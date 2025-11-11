import anthropic
from typing import List, Optional, Dict, Any
from logger import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum number of sequential tool calling rounds per query
    MAX_TOOL_ROUNDS = 2

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

**CAPACIDAD DE BÚSQUEDA MÚLTIPLE**:
- Puedes realizar hasta 2 búsquedas secuenciales si es necesario
- Después de recibir resultados, las herramientas permanecen disponibles
- Usa múltiples búsquedas para:
  ✅ Combinar información de diferentes fuentes
  ✅ Profundizar en aspectos mencionados en primeros resultados
  ✅ Buscar personas → luego buscar artículos específicos sobre ellas
- NO busques redundantemente la misma información
- Si los primeros resultados son suficientes, responde directamente

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

    # Round-specific instructions for adaptive prompting
    ROUND_SPECIFIC_INSTRUCTIONS = {
        1: "\n\n**[Ronda 1/2]** Usa herramientas si necesitas información específica. Podrás solicitar más búsquedas después de ver resultados.",
        2: "\n\n**[Ronda 2/2 - FINAL]** Última oportunidad para usar herramientas. Si tienes información suficiente, proporciona tu respuesta final."
    }

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def _call_api(self, messages: List[Dict[str, Any]], system_content: str,
                  tools: Optional[List] = None):
        """
        Make a single API call to Claude.

        Centralizes API calling logic to avoid duplication in loop.

        Args:
            messages: Conversation messages so far
            system_content: System prompt (with history if available)
            tools: Tool definitions (None to disable tools)

        Returns:
            Anthropic API response object
        """
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        logger.debug(f"API call - {len(messages)} messages, tools={'enabled' if tools else 'disabled'}")
        response = self.client.messages.create(**api_params)
        logger.debug(f"API response - stop_reason={response.stop_reason}")

        return response

    def _execute_tools_and_update_messages(self, response, messages: List[Dict[str, Any]],
                                          tool_manager) -> List[Dict[str, Any]]:
        """
        Execute all tool calls in response and update message history.

        This method modifies the conversation to include:
        1. Assistant's tool_use content blocks
        2. User's tool_result content blocks

        Args:
            response: API response containing tool_use blocks
            messages: Current message history
            tool_manager: Manager to execute tools

        Returns:
            Updated messages list with tool execution results

        Raises:
            Exception: If tool execution fails (fail-fast strategy)
        """
        # Add assistant's tool use to messages
        messages.append({"role": "assistant", "content": response.content})

        # Execute all tools and collect results
        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                logger.info(f"Executing tool: {content_block.name}")
                logger.debug(f"Tool input: {content_block.input}")

                try:
                    result = tool_manager.execute_tool(
                        content_block.name,
                        **content_block.input
                    )
                    logger.debug(f"Tool result length: {len(result)} chars")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": result
                    })
                except Exception as e:
                    logger.error(f"Tool execution failed: {e}", exc_info=True)
                    # Fail-fast: propagate exception immediately
                    raise

        # Add tool results as user message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        return messages

    def _extract_text_response(self, response) -> str:
        """
        Extract text content from API response.

        Handles responses that may have mixed content blocks.

        Args:
            response: Anthropic API response

        Returns:
            Text content from response
        """
        for block in response.content:
            if hasattr(block, 'text'):
                return block.text

        logger.warning("No text content found in response")
        return ""

    def _build_system_prompt(self, conversation_history: Optional[str],
                            round_number: int) -> str:
        """
        Build system content with optional conversation history and round-specific instructions.

        Args:
            conversation_history: Previous conversation context
            round_number: Current tool execution round (1 or 2)

        Returns:
            Complete system prompt string with adaptive instructions
        """
        # Start with base prompt
        prompt = self.SYSTEM_PROMPT

        # Add round-specific instructions if available
        if round_number in self.ROUND_SPECIFIC_INSTRUCTIONS:
            prompt += self.ROUND_SPECIFIC_INSTRUCTIONS[round_number]

        # Add conversation history if provided
        if conversation_history:
            prompt = f"{prompt}\n\nPrevious conversation:\n{conversation_history}"

        return prompt

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with up to 2 sequential tool calling rounds.

        Supports multi-round tool calling where Claude can use tools, see results,
        and decide to use tools again or provide a final answer.

        Architecture:
        - Round 1: Initial query → Claude (with tools) → potential tool_use
        - Round 2: Tool results → Claude (with tools) → potential tool_use
        - Terminate: No tool_use, max rounds reached, or error

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

            # Initialize conversation state for this query
            current_round = 0
            messages = [{"role": "user", "content": query}]

            # Main loop: Up to MAX_TOOL_ROUNDS iterations
            while current_round < self.MAX_TOOL_ROUNDS:
                current_round += 1
                logger.info(f"Starting tool round {current_round}/{self.MAX_TOOL_ROUNDS}")

                # Build adaptive system prompt for this round
                system_content = self._build_system_prompt(conversation_history, current_round)

                # Make API call with tools available
                response = self._call_api(messages, system_content, tools)

                # Termination condition 1: No tool use requested
                if response.stop_reason != "tool_use":
                    logger.info("Claude provided direct answer - terminating tool loop")
                    return self._extract_text_response(response)

                # Termination condition 2: Tool use but no tool_manager
                if not tool_manager:
                    logger.warning("Tool use requested but no tool_manager provided")
                    return self._extract_text_response(response)

                # Execute tools and accumulate conversation
                logger.info(f"Tool use requested in round {current_round}")
                messages = self._execute_tools_and_update_messages(
                    response, messages, tool_manager
                )

                # Check if we've reached max rounds
                if current_round >= self.MAX_TOOL_ROUNDS:
                    logger.info("Max tool rounds reached - making final API call")
                    system_content = self._build_system_prompt(conversation_history, current_round)
                    final_response = self._call_api(messages, system_content, tools=None)
                    return self._extract_text_response(final_response)

            # Safeguard (should never reach here, but defensive programming)
            logger.warning("Unexpectedly exited tool loop")
            return "Unable to generate response after maximum tool rounds."

        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            raise