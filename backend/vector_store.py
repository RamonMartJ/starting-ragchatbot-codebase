import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from models import Article, ArticleChunk
from sentence_transformers import SentenceTransformer
import json

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
        """
        Add article information to the catalog for semantic search.

        Workflow:
        1. Serialize people list to JSON string for ChromaDB storage
        2. Store article metadata including title, link, and people
        3. Use article title as unique ID for fast lookup

        Args:
            article: Article object with metadata and people list
        """
        article_text = article.title

        # Serialize people list to JSON for storage
        people_json = json.dumps([p.dict() for p in article.people]) if article.people else "[]"

        print(f"[DEBUG VectorStore] Adding article: {article.title}")
        print(f"[DEBUG VectorStore] People JSON ({len(article.people)} people): {people_json[:100]}...")

        self.article_catalog.add(
            documents=[article_text],
            metadatas=[{
                "title": article.title,
                "article_link": article.article_link,
                "people": people_json  # Store as JSON string
            }],
            ids=[article.title]
        )
        print(f"[DEBUG VectorStore] Successfully added to article_catalog")

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

    def get_people_from_article(self, article_title: str) -> List[Dict[str, Any]]:
        """
        Get all people mentioned in a specific article.

        Workflow:
        1. Retrieve article metadata from article_catalog using title as ID
        2. Deserialize people JSON string to list of dictionaries
        3. Return list of people with all their fields

        Args:
            article_title: Title of the article

        Returns:
            List of dictionaries with person information
        """
        try:
            # Get article by ID (title is the ID)
            results = self.article_catalog.get(ids=[article_title])
            if results and 'metadatas' in results and results['metadatas']:
                metadata = results['metadatas'][0]
                people_json = metadata.get('people', '[]')
                people_list = json.loads(people_json)
                return people_list
            return []
        except Exception as e:
            print(f"Error getting people from article: {e}")
            return []

    def find_articles_by_person(self, person_name: str) -> List[Dict[str, str]]:
        """
        Find all articles that mention a specific person.

        Workflow:
        1. Get all articles from article_catalog
        2. For each article, deserialize people JSON
        3. Check if person_name matches any person (case-insensitive)
        4. Return list of matching articles with title and link

        Args:
            person_name: Name of the person to search for

        Returns:
            List of dictionaries with 'title' and 'link' keys
        """
        try:
            matching_articles = []
            # Get all articles
            all_articles = self.article_catalog.get()

            if all_articles and 'metadatas' in all_articles:
                for metadata in all_articles['metadatas']:
                    people_json = metadata.get('people', '[]')
                    people_list = json.loads(people_json)

                    # Check if person_name matches any person in this article
                    for person in people_list:
                        if person_name.lower() in person.get('nombre', '').lower():
                            matching_articles.append({
                                'title': metadata.get('title'),
                                'link': metadata.get('article_link')
                            })
                            break  # Avoid adding same article multiple times

            return matching_articles
        except Exception as e:
            print(f"Error finding articles by person: {e}")
            return []

    def find_people_by_role(self, role: str) -> List[Dict[str, Any]]:
        """
        Find all people with a specific role/cargo across all articles.

        Workflow:
        1. Get all articles from article_catalog
        2. For each article, deserialize people JSON
        3. Check if role matches person's cargo (case-insensitive)
        4. Return list of matching people with article context

        Args:
            role: Role/cargo to search for (e.g., "Periodista", "Presidente")

        Returns:
            List of dictionaries with person info and article_title
        """
        try:
            matching_people = []
            # Get all articles
            all_articles = self.article_catalog.get()

            if all_articles and 'metadatas' in all_articles:
                for metadata in all_articles['metadatas']:
                    people_json = metadata.get('people', '[]')
                    people_list = json.loads(people_json)
                    article_title = metadata.get('title')

                    # Check if role matches any person's cargo in this article
                    for person in people_list:
                        person_cargo = person.get('cargo', '')
                        if person_cargo and role.lower() in person_cargo.lower():
                            # Add article context to person info
                            person_with_context = person.copy()
                            person_with_context['article_title'] = article_title
                            person_with_context['article_link'] = metadata.get('article_link')
                            matching_people.append(person_with_context)

            return matching_people
        except Exception as e:
            print(f"Error finding people by role: {e}")
            return []

    def get_all_people_with_frequency(self) -> List[Dict[str, Any]]:
        """
        Get all people mentioned across all articles, ordered by frequency of appearance.

        Workflow:
        1. Get all articles from article_catalog
        2. For each article, deserialize people JSON
        3. Count appearances by person name (case-insensitive)
        4. Consolidate information for each unique person
        5. Sort by frequency (most mentioned first)
        6. Return list with person info, articles, and frequency

        Returns:
            List of dictionaries with:
            - nombre: Person's name
            - frecuencia: Number of articles they appear in
            - cargos: List of unique roles they have
            - organizaciones: List of unique organizations
            - articulos: List of dicts with article_title and article_link
            - datos_interes: Consolidated interesting facts
        """
        try:
            # Dictionary to track people by name (case-insensitive key)
            people_map = {}

            # Get all articles
            all_articles = self.article_catalog.get()

            if all_articles and 'metadatas' in all_articles:
                for metadata in all_articles['metadatas']:
                    people_json = metadata.get('people', '[]')
                    people_list = json.loads(people_json)
                    article_title = metadata.get('title')
                    article_link = metadata.get('article_link')

                    # Process each person in this article
                    for person in people_list:
                        nombre = person.get('nombre', '')
                        if not nombre:
                            continue

                        # Use lowercase name as key for deduplication
                        nombre_key = nombre.lower()

                        # Initialize person entry if first time seeing them
                        if nombre_key not in people_map:
                            people_map[nombre_key] = {
                                'nombre': nombre,  # Keep original capitalization
                                'frecuencia': 0,
                                'cargos': set(),
                                'organizaciones': set(),
                                'articulos': [],
                                'datos_interes': []
                            }

                        # Update person data
                        person_entry = people_map[nombre_key]
                        person_entry['frecuencia'] += 1

                        # Add cargo if present
                        cargo = person.get('cargo')
                        if cargo:
                            person_entry['cargos'].add(cargo)

                        # Add organization if present
                        org = person.get('organizacion')
                        if org:
                            person_entry['organizaciones'].add(org)

                        # Add article reference
                        person_entry['articulos'].append({
                            'title': article_title,
                            'link': article_link
                        })

                        # Add datos_interes if present
                        datos = person.get('datos_interes')
                        if datos:
                            person_entry['datos_interes'].append(datos)

            # Convert sets to lists and prepare final output
            result = []
            for person_data in people_map.values():
                result.append({
                    'nombre': person_data['nombre'],
                    'frecuencia': person_data['frecuencia'],
                    'cargos': list(person_data['cargos']),
                    'organizaciones': list(person_data['organizaciones']),
                    'articulos': person_data['articulos'],
                    'datos_interes': person_data['datos_interes']
                })

            # Sort by frequency (descending)
            result.sort(key=lambda x: x['frecuencia'], reverse=True)

            return result
        except Exception as e:
            print(f"Error getting all people with frequency: {e}")
            return []
