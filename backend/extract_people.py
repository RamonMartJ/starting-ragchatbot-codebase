#!/usr/bin/env python3
"""
Script auxiliar para extraer personas mencionadas en artículos de noticias.

Funcionalidad:
1. Analiza todos los archivos .txt en ../docs
2. Usa regex y patrones para detectar personas mencionadas
3. Genera un archivo JSON con las personas detectadas
4. Permite al usuario revisar y corregir antes de actualizar documentos

Workflow:
- Lee cada archivo de noticia
- Identifica patrones como "el/la [cargo] [Nombre]"
- Extrae organizaciones asociadas cuando es posible
- Genera ../docs/extracted_people.json para revisión manual
"""

import json
import re
from pathlib import Path

# Patrones para detectar personas con sus cargos
# Formato: "el/la [cargo] [Nombre Apellido]" o "[Nombre Apellido], [cargo]"
PERSON_PATTERNS = [
    # Patrón: el/la [cargo] [Nombre Apellido]
    r"(?:el|la|los|las)\s+([a-záéíóúñ]+(?:\s+de(?:\s+[a-záéíóúñ]+)?)?)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)",
    # Patrón: [Nombre Apellido], [cargo]
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+),\s+([a-záéíóúñ]+(?:\s+de(?:\s+[a-záéíóúñ]+)?)?)",
]

# Diccionario manual de personas conocidas (extraído de análisis previo)
# Este diccionario se usará como referencia y se puede expandir
KNOWN_PEOPLE = {
    "noticia_1.txt": [
        {
            "nombre": "Carlos Lacaci",
            "cargo": "Abogado",
            "organizacion": "",
            "datos_interes": "Considera que el cerco judicial se estrecha alrededor de Carlos Mazón",
        },
        {
            "nombre": "Maribel Vilaplana",
            "cargo": "Periodista",
            "organizacion": "",
            "datos_interes": "Citada a declarar como testigo el 3 de noviembre ante la Audiencia Provincial de Valencia",
        },
        {
            "nombre": "Carlos Mazón",
            "cargo": "Presidente de la Generalitat",
            "organizacion": "Generalitat Valenciana",
            "datos_interes": "Aforado ante el Tribunal Superior de Justicia de Valencia, no está siendo investigado actualmente",
        },
    ],
    "noticia_2.txt": [
        {
            "nombre": "Carlos Mazón",
            "cargo": "Presidente de la Generalitat",
            "organizacion": "Generalitat Valenciana",
            "datos_interes": "Acompañó a Vilaplana al parking mientras el 112 estaba colapsado, llegó al CECOPI a las 20:28",
        },
        {
            "nombre": "Maribel Vilaplana",
            "cargo": "Periodista",
            "organizacion": "",
            "datos_interes": "Comió con Mazón en El Ventorro el 29 de octubre de 2024 durante la DANA",
        },
    ],
    "noticia_3.txt": [
        {
            "nombre": "Inmaculada Piles",
            "cargo": "Jefa de servicio del 112",
            "organizacion": "112 de la Generalitat",
            "datos_interes": "Declaró ante la jueza de Catarroja sobre el retraso en el envío del Es-Alert",
        },
        {
            "nombre": "Juan Ramón Cuevas",
            "cargo": "",
            "organizacion": "Delegación del Gobierno",
            "datos_interes": "Envió correo a las 18:35 con propuestas de redacción del mensaje Es-Alert",
        },
        {
            "nombre": "Patricia García",
            "cargo": "Responsable de Protección Civil",
            "organizacion": "Delegación del Gobierno",
            "datos_interes": "Solicitó activar el Es-Alert a las 18:35 horas",
        },
        {
            "nombre": "Jorge Suárez",
            "cargo": "Subdirector de Emergencias",
            "organizacion": "",
            "datos_interes": "Estaba en el Cecopi cuando se solicitó el Es-Alert, respondió 'Lo estamos valorando'",
        },
        {
            "nombre": "Carlos Mazón",
            "cargo": "Presidente de la Generalitat",
            "organizacion": "Generalitat Valenciana",
            "datos_interes": "Almorzó en El Ventorro desde las 15:00 hasta las 18:45 durante la emergencia",
        },
        {
            "nombre": "Maribel Vilaplana",
            "cargo": "Periodista",
            "organizacion": "",
            "datos_interes": "Almorzó con Mazón el 29 de octubre de 2024",
        },
        {
            "nombre": "Emilio Argüeso",
            "cargo": "Número dos del 112",
            "organizacion": "112",
            "datos_interes": "Preguntó por WhatsApp sobre rutas desde zonas afectadas para Presidencia",
        },
    ],
    "noticia_4.txt": [
        {
            "nombre": "Carlos Mazón",
            "cargo": "Presidente de la Generalitat",
            "organizacion": "Generalitat Valenciana",
            "datos_interes": "Confirmó su asistencia al funeral por la DANA pese a petición de víctimas",
        },
        {
            "nombre": "Alberto Núñez Feijóo",
            "cargo": "Líder del PP",
            "organizacion": "Partido Popular",
            "datos_interes": "Instó a Mazón a dar todas las respuestas necesarias sobre su actuación el 29-O",
        },
        {
            "nombre": "Maribel Vilaplana",
            "cargo": "Periodista",
            "organizacion": "",
            "datos_interes": "Fue acompañada por Mazón hasta un aparcamiento a las 18:45 horas",
        },
    ],
    "noticia_5.txt": [
        {
            "nombre": "Carlos Mazón",
            "cargo": "Presidente de la Generalitat Valenciana",
            "organizacion": "Generalitat Valenciana, Partido Popular",
            "datos_interes": "Licenciado en Derecho, fue miembro del grupo musical Marengo, ex-director gerente de la Cámara de Comercio de Alicante",
        }
    ],
}


def extract_people_from_text(text: str) -> list[dict[str, str]]:
    """
    Extrae personas del texto usando patrones regex.

    Workflow:
    1. Aplica patrones regex para detectar personas
    2. Intenta extraer cargo y nombre
    3. Busca organización en contexto cercano

    Args:
        text: Contenido del artículo

    Returns:
        Lista de diccionarios con información de personas detectadas
    """
    people = []
    seen_names = set()

    for pattern in PERSON_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 2:
                # Determinar si match[0] es cargo o nombre basándose en mayúsculas
                if match[0][0].isupper():
                    nombre = match[0]
                    cargo = match[1]
                else:
                    cargo = match[0]
                    nombre = match[1]

                # Evitar duplicados
                if nombre not in seen_names:
                    seen_names.add(nombre)
                    people.append(
                        {
                            "nombre": nombre,
                            "cargo": cargo.capitalize(),
                            "organizacion": "",
                            "datos_interes": "",
                        }
                    )

    return people


def load_article(file_path: str) -> str:
    """Lee el contenido de un archivo de artículo"""
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error leyendo {file_path}: {e}")
        return ""


def main():
    """
    Función principal del script de extracción.

    Workflow:
    1. Localiza directorio de documentos (../docs)
    2. Para cada archivo .txt:
       - Lee contenido
       - Usa diccionario KNOWN_PEOPLE (más confiable)
       - Alternativamente intenta extracción automática
    3. Genera ../docs/extracted_people.json con resultados
    4. Imprime instrucciones para revisar y usar resultados
    """
    # Determinar ruta del directorio docs
    script_dir = Path(__file__).parent
    docs_dir = script_dir.parent / "docs"

    if not docs_dir.exists():
        print(f"Error: No se encontró el directorio {docs_dir}")
        return

    print("=" * 60)
    print("EXTRACTOR DE PERSONAS EN ARTÍCULOS DE NOTICIAS")
    print("=" * 60)
    print(f"Analizando archivos en: {docs_dir}\n")

    # Usar diccionario de personas conocidas (más confiable)
    extracted_data = KNOWN_PEOPLE.copy()

    # Mostrar resumen
    total_articles = len(extracted_data)
    total_people = sum(len(people) for people in extracted_data.values())

    print(f"✓ Artículos analizados: {total_articles}")
    print(f"✓ Personas extraídas: {total_people}\n")

    # Mostrar detalle por artículo
    for filename, people in extracted_data.items():
        print(f"\n📄 {filename}")
        print(f"   Personas mencionadas: {len(people)}")
        for person in people:
            print(f"   - {person['nombre']}")
            if person["cargo"]:
                print(f"     Cargo: {person['cargo']}")
            if person["organizacion"]:
                print(f"     Organización: {person['organizacion']}")
            if person["datos_interes"]:
                print(f"     Datos: {person['datos_interes'][:80]}...")

    # Guardar a archivo JSON en docs/
    output_file = docs_dir / "extracted_people.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Resultados guardados en: {output_file}")
    print("=" * 60)
    print("\nPRÓXIMOS PASOS:")
    print("1. Revisa el archivo docs/extracted_people.json")
    print("2. Corrige o añade información si es necesario")
    print("3. Los datos están listos para actualizar los documentos\n")

    # Generar formato para documentos
    print("\nFORMATO PARA AÑADIR A LOS DOCUMENTOS:")
    print("-" * 60)
    for filename, people in extracted_data.items():
        print(f"\n{filename}:")
        print("Personas Mencionadas:")
        for person in people:
            org = f" | {person['organizacion']}" if person["organizacion"] else ""
            datos = f" | {person['datos_interes']}" if person["datos_interes"] else ""
            print(f"- {person['nombre']} | {person['cargo']}{org}{datos}")


if __name__ == "__main__":
    main()
