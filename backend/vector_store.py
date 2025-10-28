import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from models import Article, ArticleChunk
from sentence_transformers import SentenceTransformer

@dataclass
class SearchResults:
    """Container for search results with metadata"""
    documents: List[str]
    metadata: List[Dict[str, Any]]
    distances: List[float]
    error: Optional[str] = None
    
    @classmethod
    def from_chroma(cls, chroma_results: Dict) -> 'SearchResults':
        """Create SearchResults from ChromaDB query results"""
        return cls(
            documents=chroma_results['documents'][0] if chroma_results['documents'] else [],
            metadata=chroma_results['metadatas'][0] if chroma_results['metadatas'] else [],
            distances=chroma_results['distances'][0] if chroma_results['distances'] else []
        )
    
    @classmethod
    def empty(cls, error_msg: str) -> 'SearchResults':
        """Create empty results with error message"""
        return cls(documents=[], metadata=[], distances=[], error=error_msg)
    
    def is_empty(self) -> bool:
        """Check if results are empty"""
        return len(self.documents) == 0

class VectorStore:
    """Vector storage using ChromaDB for news article content and metadata"""

    def __init__(self, chroma_path: str, embedding_model: str, max_results: int = 5):
        self.max_results = max_results
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Set up sentence transformer embedding function
        self.embedding_function = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Create collections for different types of data
        self.article_catalog = self._create_collection("article_catalog")  # Article titles for semantic matching
        self.article_content = self._create_collection("article_content")  # Actual article content
    
    def _create_collection(self, name: str):
        """Create or get a ChromaDB collection"""
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_function
        )
    
    def search(self,
               query: str,
               article_title: Optional[str] = None,
               limit: Optional[int] = None) -> SearchResults:
        """
        Main search interface that handles article resolution and content search.

        Args:
            query: What to search for in article content
            article_title: Optional article title to filter by
            limit: Maximum results to return

        Returns:
            SearchResults object with documents and metadata
        """
        # Step 1: Resolve article title if provided
        resolved_title = None
        if article_title:
            resolved_title = self._resolve_article_title(article_title)
            if not resolved_title:
                return SearchResults.empty(f"No article found matching '{article_title}'")

        # Step 2: Build filter for content search
        filter_dict = self._build_filter(resolved_title)

        # Step 3: Search article content
        # Use provided limit or fall back to configured max_results
        search_limit = limit if limit is not None else self.max_results

        try:
            results = self.article_content.query(
                query_texts=[query],
                n_results=search_limit,
                where=filter_dict
            )
            return SearchResults.from_chroma(results)
        except Exception as e:
            return SearchResults.empty(f"Search error: {str(e)}")
    
    def _resolve_article_title(self, article_title: str) -> Optional[str]:
        """Use vector search to find best matching article by title"""
        try:
            results = self.article_catalog.query(
                query_texts=[article_title],
                n_results=1
            )

            if results['documents'][0] and results['metadatas'][0]:
                # Return the title (which is the ID)
                return results['metadatas'][0][0]['title']
        except Exception as e:
            print(f"Error resolving article title: {e}")

        return None

    def _build_filter(self, article_title: Optional[str]) -> Optional[Dict]:
        """Build ChromaDB filter from search parameters"""
        if not article_title:
            return None

        return {"article_title": article_title}
    
    def add_article_metadata(self, article: Article):
        """Add article information to the catalog for semantic search"""
        article_text = article.title

        self.article_catalog.add(
            documents=[article_text],
            metadatas=[{
                "title": article.title,
                "article_link": article.article_link,
            }],
            ids=[article.title]
        )

    def add_article_content(self, chunks: List[ArticleChunk]):
        """Add article content chunks to the vector store"""
        if not chunks:
            return

        documents = [chunk.content for chunk in chunks]
        metadatas = [{
            "article_title": chunk.article_title,
            "chunk_index": chunk.chunk_index
        } for chunk in chunks]
        # Use title with chunk index for unique IDs
        ids = [f"{chunk.article_title.replace(' ', '_').replace(':', '')}_{chunk.chunk_index}" for chunk in chunks]

        self.article_content.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def clear_all_data(self):
        """Clear all data from both collections"""
        try:
            self.client.delete_collection("article_catalog")
            self.client.delete_collection("article_content")
            # Recreate collections
            self.article_catalog = self._create_collection("article_catalog")
            self.article_content = self._create_collection("article_content")
        except Exception as e:
            print(f"Error clearing data: {e}")

    def get_existing_article_titles(self) -> List[str]:
        """Get all existing article titles from the vector store"""
        try:
            # Get all documents from the catalog
            results = self.article_catalog.get()
            if results and 'ids' in results:
                return results['ids']
            return []
        except Exception as e:
            print(f"Error getting existing article titles: {e}")
            return []

    def get_article_count(self) -> int:
        """Get the total number of articles in the vector store"""
        try:
            results = self.article_catalog.get()
            if results and 'ids' in results:
                return len(results['ids'])
            return 0
        except Exception as e:
            print(f"Error getting article count: {e}")
            return 0
    
    def get_all_articles_metadata(self) -> List[Dict[str, Any]]:
        """Get metadata for all articles in the vector store"""
        try:
            results = self.article_catalog.get()
            if results and 'metadatas' in results:
                return results['metadatas']
            return []
        except Exception as e:
            print(f"Error getting articles metadata: {e}")
            return []

    def get_article_link(self, article_title: str) -> Optional[str]:
        """Get article link for a given article title"""
        try:
            # Get article by ID (title is the ID)
            results = self.article_catalog.get(ids=[article_title])
            if results and 'metadatas' in results and results['metadatas']:
                metadata = results['metadatas'][0]
                return metadata.get('article_link')
            return None
        except Exception as e:
            print(f"Error getting article link: {e}")
            return None
    