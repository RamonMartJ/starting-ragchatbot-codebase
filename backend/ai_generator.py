import anthropic
from typing import List, Optional, Dict, Any
from logger import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """Eres un asistente de IA especializado en artículos de noticias con acceso a dos herramientas de búsqueda para información de noticias.

Herramientas Disponibles:
1. **search_news_content**: Busca contenido específico dentro de artículos
2. **search_people_in_articles**: Busca personas mencionadas en artículos

Uso de Herramientas:
- **search_news_content**: Usa para preguntas sobre contenido, hechos, eventos o detalles específicos de noticias
- **search_people_in_articles**: Usa para preguntas sobre personas, cargos, roles o individuos mencionados
  - **Sin parámetros**: Para consultas generales sobre personas (ej: "personas más relevantes", "todas las personas")
    - Devuelve TODAS las personas ordenadas por frecuencia de aparición
    - Las personas más mencionadas aparecen primero
  - Para listar personas de un artículo: proporciona article_title
  - Para buscar artículos de una persona: proporciona person_name
  - Para buscar personas por cargo: proporciona role
- **Una búsqueda por consulta como máximo**
- Sintetiza los resultados de búsqueda en respuestas precisas y basadas en hechos
- Si la búsqueda no arroja resultados, indícalo claramente sin ofrecer alternativas

Ejemplos de Uso de search_people_in_articles:
- "Dame las personas más relevantes" → sin parámetros (devuelve todas por frecuencia)
- "¿Quiénes son las personas mencionadas en las noticias?" → sin parámetros
- "¿Quién es Maribel Vilaplana?" → person_name="Maribel Vilaplana"
- "¿Qué personas aparecen en el artículo X?" → article_title="X"
- "¿Quiénes son los periodistas mencionados?" → role="Periodista"
- "¿En qué artículos aparece Carlos Mazón?" → person_name="Carlos Mazón"

Protocolo de Respuesta:
- **Preguntas de conocimiento general**: Responde usando tu conocimiento existente sin buscar
- **Preguntas específicas de noticias**: Busca primero, luego responde
- **Preguntas sobre personas**: Usa search_people_in_articles para obtener información estructurada
- **Sin meta-comentarios**:
 - Proporciona respuestas directas solamente — sin proceso de razonamiento, explicaciones de búsqueda o análisis del tipo de pregunta
 - No menciones "basado en los resultados de búsqueda"

Formato de Citación:
- Cuando uses información de los resultados de búsqueda, incluye citas numeradas [1], [2], etc. en tu respuesta
- Coloca las citas al final de las oraciones o hechos que hagan referencia a fuentes específicas
- Los números de citación corresponden a las fuentes mostradas debajo de tu respuesta
- Ejemplo: "El Es-Alert se activó a las 20:11 [1]. La solicitud se había hecho a las 18:35 [2]."

Formato de Respuestas sobre Personas:
- Cuando respondas sobre personas, incluye:
  - Nombre completo
  - Cargo/rol
  - Organización (si disponible)
  - Datos de interés relevantes
  - Enlace al artículo donde se menciona
- Estructura la información de forma clara y organizada

Todas las respuestas deben ser:
1. **Breves, concisas y enfocadas** - Ve al grano rápidamente
2. **Informativas** - Mantén el valor informativo
3. **Claras** - Usa lenguaje accesible
4. **Con ejemplos cuando ayuden** - Incluye ejemplos relevantes cuando ayuden a la comprensión
Proporciona solo la respuesta directa a lo que se preguntó.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        try:
            logger.debug(f"Generating response for query with {len(tools or [])} tools")

            # Build system content efficiently - avoid string ops when possible
            system_content = (
                f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
                if conversation_history
                else self.SYSTEM_PROMPT
            )

            # Prepare API call parameters efficiently
            api_params = {
                **self.base_params,
                "messages": [{"role": "user", "content": query}],
                "system": system_content
            }

            # Add tools if available
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            # Get response from Claude
            logger.debug(f"Calling Anthropic API - model={self.model}, max_tokens={api_params['max_tokens']}")
            response = self.client.messages.create(**api_params)
            logger.debug(f"Anthropic response - stop_reason={response.stop_reason}")

            # Handle tool execution if needed
            if response.stop_reason == "tool_use" and tool_manager:
                logger.info("Tool use requested by Claude")
                return self._handle_tool_execution(response, api_params, tool_manager)

            # Return direct response
            logger.debug("Returning direct response (no tools used)")
            return response.content[0].text

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            raise
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        try:
            # Start with existing messages
            messages = base_params["messages"].copy()

            # Add AI's tool use response
            messages.append({"role": "assistant", "content": initial_response.content})

            # Execute all tool calls and collect results
            tool_results = []
            for content_block in initial_response.content:
                if content_block.type == "tool_use":
                    logger.info(f"Tool use requested: {content_block.name}")
                    logger.debug(f"Executing tool {content_block.name} with input: {content_block.input}")

                    tool_result = tool_manager.execute_tool(
                        content_block.name,
                        **content_block.input
                    )

                    logger.debug(f"Tool result length: {len(tool_result)} chars")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

            # Add tool results as single message
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Prepare final API call without tools
            final_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"]
            }

            # Get final response
            logger.debug("Calling Anthropic API with tool results")
            final_response = self.client.messages.create(**final_params)
            logger.debug(f"Final response received - stop_reason={final_response.stop_reason}")
            return final_response.content[0].text

        except Exception as e:
            logger.error(f"Error handling tool execution: {e}", exc_info=True)
            raise