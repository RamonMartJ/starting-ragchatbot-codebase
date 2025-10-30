from typing import List, Tuple, Optional, Dict
import os
from document_processor import DocumentProcessor
from vector_store import VectorStore
from ai_generator import AIGenerator
from session_manager import SessionManager
from search_tools import ToolManager, ArticleSearchTool, PeopleSearchTool
from models import Article, ArticleChunk

class RAGSystem:
    """Main orchestrator for the Retrieval-Augmented Generation system"""

    def __init__(self, config):
        self.config = config

        # Initialize core components
        self.document_processor = DocumentProcessor(config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        self.vector_store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
        self.ai_generator = AIGenerator(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)
        self.session_manager = SessionManager(config.MAX_HISTORY)

        # Initialize search tools
        self.tool_manager = ToolManager()

        # Register article content search tool
        self.search_tool = ArticleSearchTool(self.vector_store)
        self.tool_manager.register_tool(self.search_tool)

        # Register people search tool
        self.people_tool = PeopleSearchTool(self.vector_store)
        self.tool_manager.register_tool(self.people_tool)
    
    def add_article_document(self, file_path: str) -> Tuple[Article, int]:
        """
        Add a single article document to the knowledge base.

        Args:
            file_path: Path to the article document

        Returns:
            Tuple of (Article object, number of chunks created)
        """
        try:
            print(f"[DEBUG] Processing article: {file_path}")
            # Process the document
            article, article_chunks = self.document_processor.process_article_document(file_path)

            print(f"[DEBUG] Article '{article.title}' has {len(article.people)} people")
            for person in article.people:
                print(f"[DEBUG]   - {person.nombre} | {person.cargo}")

            # Add article metadata to vector store for semantic search
            self.vector_store.add_article_metadata(article)
            print(f"[DEBUG] Added article metadata to vector store")

            # Add article content chunks to vector store
            self.vector_store.add_article_content(article_chunks)
            print(f"[DEBUG] Added {len(article_chunks)} chunks to vector store")

            return article, len(article_chunks)
        except Exception as e:
            print(f"[ERROR] Error processing article document {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return None, 0
    
    def add_articles_folder(self, folder_path: str, clear_existing: bool = False) -> Tuple[int, int]:
        """
        Add all article documents from a folder.

        Args:
            folder_path: Path to folder containing article documents
            clear_existing: Whether to clear existing data first

        Returns:
            Tuple of (total articles added, total chunks created)
        """
        total_articles = 0
        total_chunks = 0

        # Clear existing data if requested
        if clear_existing:
            print("Clearing existing data for fresh rebuild...")
            self.vector_store.clear_all_data()

        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return 0, 0

        # Get existing article titles to avoid re-processing
        existing_article_titles = set(self.vector_store.get_existing_article_titles())

        # Process each file in the folder
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path) and file_name.lower().endswith(('.pdf', '.docx', '.txt')):
                try:
                    # Check if this article might already exist
                    # We'll process the document to get the article ID, but only add if new
                    article, article_chunks = self.document_processor.process_article_document(file_path)

                    if article and article.title not in existing_article_titles:
                        # This is a new article - add it to the vector store
                        self.vector_store.add_article_metadata(article)
                        self.vector_store.add_article_content(article_chunks)
                        total_articles += 1
                        total_chunks += len(article_chunks)
                        print(f"Added new article: {article.title} ({len(article_chunks)} chunks)")
                        existing_article_titles.add(article.title)
                    elif article:
                        print(f"Article already exists: {article.title} - skipping")
                except Exception as e:
                    print(f"Error processing {file_name}: {e}")

        return total_articles, total_chunks
    
    def query(self, query: str, session_id: Optional[str] = None) -> Tuple[str, List[str]]:
        """
        Process a user query using the RAG system with tool-based search.

        Args:
            query: User's question
            session_id: Optional session ID for conversation context

        Returns:
            Tuple of (response, sources list - empty for tool-based approach)
        """
        # Create prompt for the AI with clear instructions
        prompt = f"""Responde a esta pregunta sobre artículos de noticias: {query}"""

        # Get conversation history if session exists
        history = None
        if session_id:
            history = self.session_manager.get_conversation_history(session_id)

        # Generate response using AI with tools
        response = self.ai_generator.generate_response(
            query=prompt,
            conversation_history=history,
            tools=self.tool_manager.get_tool_definitions(),
            tool_manager=self.tool_manager
        )

        # Get sources from the search tool
        sources = self.tool_manager.get_last_sources()

        # Reset sources after retrieving them
        self.tool_manager.reset_sources()

        # Update conversation history
        if session_id:
            self.session_manager.add_exchange(session_id, query, response)

        # Return response with sources from tool searches
        return response, sources

    def get_article_analytics(self) -> Dict:
        """Get analytics about the article catalog"""
        return {
            "total_articles": self.vector_store.get_article_count(),
            "article_titles": self.vector_store.get_existing_article_titles()
        }