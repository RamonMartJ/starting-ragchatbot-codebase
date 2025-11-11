import os
import re

from models import Article, ArticleChunk, Person


class DocumentProcessor:
    """Processes news article documents and extracts structured information"""

    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def read_file(self, file_path: str) -> str:
        """Read content from file with UTF-8 encoding"""
        try:
            with open(file_path, encoding="utf-8") as file:
                return file.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try with error handling
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                return file.read()

    def chunk_text(self, text: str) -> list[str]:
        """Split text into sentence-based chunks with overlap using config settings"""

        # Clean up the text
        text = re.sub(r"\s+", " ", text.strip())  # Normalize whitespace

        # Better sentence splitting that handles abbreviations
        # This regex looks for periods followed by whitespace and capital letters
        # but ignores common abbreviations
        sentence_endings = re.compile(
            r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\!|\?)\s+(?=[A-Z])"
        )
        sentences = sentence_endings.split(text)

        # Clean sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        i = 0

        while i < len(sentences):
            current_chunk = []
            current_size = 0

            # Build chunk starting from sentence i
            for j in range(i, len(sentences)):
                sentence = sentences[j]

                # Calculate size with space
                space_size = 1 if current_chunk else 0
                total_addition = len(sentence) + space_size

                # Check if adding this sentence would exceed chunk size
                if current_size + total_addition > self.chunk_size and current_chunk:
                    break

                current_chunk.append(sentence)
                current_size += total_addition

            # Add chunk if we have content
            if current_chunk:
                chunks.append(" ".join(current_chunk))

                # Calculate overlap for next chunk
                if hasattr(self, "chunk_overlap") and self.chunk_overlap > 0:
                    # Find how many sentences to overlap
                    overlap_size = 0
                    overlap_sentences = 0

                    # Count backwards from end of current chunk
                    for k in range(len(current_chunk) - 1, -1, -1):
                        sentence_len = len(current_chunk[k]) + (
                            1 if k < len(current_chunk) - 1 else 0
                        )
                        if overlap_size + sentence_len <= self.chunk_overlap:
                            overlap_size += sentence_len
                            overlap_sentences += 1
                        else:
                            break

                    # Move start position considering overlap
                    next_start = i + len(current_chunk) - overlap_sentences
                    i = max(next_start, i + 1)  # Ensure we make progress
                else:
                    # No overlap - move to next sentence after current chunk
                    i += len(current_chunk)
            else:
                # No sentences fit, move to next
                i += 1

        return chunks

    def _parse_person_line(self, line: str) -> Person:
        """
        Parse a person line from the Personas Mencionadas section.

        Workflow:
        1. Remove leading "- " from line
        2. Split by "|" separator
        3. Extract and strip each field: Nombre | Cargo | Organización | Datos
        4. Create Person object with extracted fields

        Format: - Nombre | Cargo | Organización | Datos

        Args:
            line: Line starting with "- " containing person info

        Returns:
            Person object or None if parsing fails
        """
        try:
            # Remove leading "- " and split by |
            line_content = line.lstrip("- ").strip()
            parts = [part.strip() for part in line_content.split("|")]

            print(f"[DEBUG] Parsing person line: '{line[:50]}...'")
            print(f"[DEBUG] Split into {len(parts)} parts: {parts}")

            # Ensure we have at least a name
            if not parts or not parts[0]:
                print("[WARNING] No name found in person line")
                return None

            # Extract fields (with defaults for missing parts)
            nombre = parts[0] if len(parts) > 0 else ""
            cargo = parts[1] if len(parts) > 1 else None
            organizacion = parts[2] if len(parts) > 2 else None
            datos_interes = parts[3] if len(parts) > 3 else None

            # Clean empty strings to None
            cargo = cargo if cargo and cargo.strip() else None
            organizacion = (
                organizacion if organizacion and organizacion.strip() else None
            )
            datos_interes = (
                datos_interes if datos_interes and datos_interes.strip() else None
            )

            person = Person(
                nombre=nombre,
                cargo=cargo,
                organizacion=organizacion,
                datos_interes=datos_interes,
            )
            print(f"[DEBUG] Created person: {person.nombre} ({person.cargo})")
            return person
        except Exception as e:
            print(f"[ERROR] Error parsing person line '{line}': {e}")
            import traceback

            traceback.print_exc()
            return None

    def process_article_document(
        self, file_path: str
    ) -> tuple[Article, list[ArticleChunk]]:
        """
        Process a news article document with expected format:
        Line 1: Titular: [título]
        Lines 2-N: Personas Mencionadas: (optional)
                   - Nombre | Cargo | Organización | Datos
        Lines N+1-M: Article content (summary and body)
        Last line: Enlace: [url]

        Workflow:
        1. Extract article title from "Titular:" line
        2. Extract people from "Personas Mencionadas:" section (if present)
        3. Extract article link from "Enlace:" line (if present)
        4. All remaining content is the article body
        5. Chunk the article body using sentence-based chunking
        6. Return Article object and list of ArticleChunks
        """
        content = self.read_file(file_path)
        filename = os.path.basename(file_path)

        lines = content.strip().split("\n")

        # Initialize article metadata
        article_title = filename  # Default fallback
        article_link = None
        article_people = []
        article_content_lines = []

        # Flag para detectar sección de personas
        in_people_section = False

        # Parse article structure
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Check for title marker
            title_match = re.match(r"^Titular:\s*(.+)$", line, re.IGNORECASE)
            if title_match:
                article_title = title_match.group(1).strip()
                i += 1
                continue

            # Check for people section marker
            people_section_match = re.match(
                r"^Personas\s+Mencionadas:\s*$", line, re.IGNORECASE
            )
            if people_section_match:
                in_people_section = True
                i += 1
                continue

            # Check for link marker (ends people section if active)
            link_match = re.match(r"^Enlace:\s*(.+)$", line, re.IGNORECASE)
            if link_match:
                article_link = link_match.group(1).strip()
                in_people_section = False
                i += 1
                continue

            # Parse person line if in people section
            # Format: - Nombre | Cargo | Organización | Datos
            if in_people_section and line.startswith("-"):
                person = self._parse_person_line(line)
                if person:
                    article_people.append(person)
                i += 1
                continue

            # Check if we've left the people section (empty line or non-person content)
            if in_people_section and line and not line.startswith("-"):
                in_people_section = False

            # All other lines are article content (skip if in people section)
            if line and not in_people_section:  # Skip empty lines and people section
                article_content_lines.append(line)

            i += 1

        # Create Article object
        article = Article(
            title=article_title, article_link=article_link, people=article_people
        )

        # Combine article content and create chunks
        article_chunks = []
        chunk_counter = 0

        if article_content_lines:
            # Join all content lines
            article_text = "\n".join(article_content_lines).strip()

            if article_text:
                # Create chunks using sentence-based chunking
                chunks = self.chunk_text(article_text)
                for chunk in chunks:
                    # Add article context to help with search relevance
                    chunk_with_context = f"Artículo '{article_title}': {chunk}"

                    article_chunk = ArticleChunk(
                        content=chunk_with_context,
                        article_title=article.title,
                        chunk_index=chunk_counter,
                    )
                    article_chunks.append(article_chunk)
                    chunk_counter += 1

        return article, article_chunks
