import json
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

# Importar las funciones de los scripts de scraping
from scrape_books import scrape_books
from scrape_hn import scrape_hacker_news

# Configuración del logging (opcional, pero útil)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="API de Scraping de Libros y Noticias",
    description="API para iniciar scraping de libros, buscar libros y obtener titulares de Hacker News.",
    version="1.0.0",
)

# --- Modelos de Datos (Pydantic) ---


class Book(BaseModel):
    Título: str
    Precio: float
    Categoría: str
    # Usar Field y alias para mapear la clave JSON con espacio al nombre del campo Python
    URL_de_la_imagen: str = Field(alias="URL de la imagen")


class Headline(BaseModel):
    title: str
    score: int
    url: str


# --- Variables Globales / Estado ---
# (Podríamos usar una base de datos real, pero por ahora leeremos del JSON)
BOOKS_FILE = "books.json"
HN_FILE = (
    "hacker_news.json"  # Aunque no lo leamos directamente para /headlines, lo definimos
)

# --- Funciones Auxiliares ---


def load_books_from_json() -> List[Dict[str, Any]]:
    """Carga los datos de los libros desde el archivo JSON."""
    try:
        with open(BOOKS_FILE, "r", encoding="utf-8") as f:
            books_data = json.load(f)
            # Validar que sea una lista (opcional pero bueno)
            if not isinstance(books_data, list):
                logging.error(
                    f"El archivo {BOOKS_FILE} no contiene una lista JSON válida."
                )
                return []
            return books_data
    except FileNotFoundError:
        logging.warning(
            f"El archivo {BOOKS_FILE} no se encontró. Ejecute /init primero."
        )
        return []
    except json.JSONDecodeError:
        logging.error(f"Error al decodificar JSON en {BOOKS_FILE}.")
        return []
    except Exception as e:
        logging.error(f"Error inesperado al leer {BOOKS_FILE}: {e}")
        return []


# --- Endpoints de la API ---


@app.post("/init", status_code=202)
async def initialize_book_scraping(background_tasks: BackgroundTasks):
    """
    Activa el scraping inicial de libros en segundo plano.
    """
    logging.info(
        "Recibida solicitud POST /init. Iniciando scraping de libros en segundo plano."
    )
    # Ejecuta la función de scraping en segundo plano
    # Puedes pasar argumentos a scrape_books si es necesario, ej: num_books=100
    background_tasks.add_task(scrape_books)
    return {"message": "El scraping de libros se ha iniciado en segundo plano."}


@app.get("/books", response_model=List[Book])
async def get_books(
    category: Optional[str] = Query(None, description="Filtrar libros por categoría"),
):
    """
    Recupera la lista de libros desde books.json.
    Permite filtrar por categoría usando un parámetro de consulta.
    """
    logging.info(f"Recibida solicitud GET /books. Categoría de filtro: {category}")
    books_data = load_books_from_json()

    if not books_data:
        # Si no hay libros, podría ser porque el archivo no existe o está vacío.
        # Devolver una lista vacía es apropiado aquí.
        return []

    if category:
        # Filtrar por categoría (insensible a mayúsculas/minúsculas y espacios)
        category_lower = category.strip().lower()
        filtered_books = [
            book
            for book in books_data
            if book.get("Categoría")
            and book["Categoría"].strip().lower() == category_lower
        ]
        logging.info(
            f"Filtrando por categoría '{category}'. Encontrados {len(filtered_books)} libros."
        )
        # Validar la estructura antes de devolver (opcional pero robusto)
        # Usamos un try-except por si algún libro en el JSON no cumple el modelo
        validated_books = []
        for book in filtered_books:
            try:
                validated_books.append(Book(**book))
            except Exception as e:
                logging.warning(
                    f"Libro inválido encontrado y omitido: {book}. Error: {e}"
                )
        return validated_books
    else:
        # Devolver todos los libros si no hay filtro de categoría
        logging.info(f"Devolviendo todos los {len(books_data)} libros.")
        # Validar la estructura antes de devolver
        validated_books = []
        for book in books_data:
            try:
                validated_books.append(Book(**book))
            except Exception as e:
                logging.warning(
                    f"Libro inválido encontrado y omitido: {book}. Error: {e}"
                )
        return validated_books


@app.get("/books/search", response_model=List[Book])
async def search_books(
    query: str = Query(
        ..., min_length=1, description="Término de búsqueda para título o categoría"
    ),
    search_in: str = Query(
        "all",
        enum=["title", "category", "all"],
        description="Campo para buscar (title, category, o all)",
    ),
):
    """
    Busca libros por título o categoría en books.json.
    """
    logging.info(
        f"Recibida solicitud GET /books/search. Query: '{query}', Search in: '{search_in}'"
    )
    books_data = load_books_from_json()

    if not books_data:
        return []

    query_lower = query.strip().lower()
    results = []

    for book in books_data:
        match = False
        # Asegurarse de que las claves existen y son strings antes de operar
        title = book.get("Título", "")
        category = book.get("Categoría", "")

        # Comprobar tipos por seguridad
        if not isinstance(title, str):
            title = ""
        if not isinstance(category, str):
            category = ""

        title_lower = title.strip().lower()
        category_lower = category.strip().lower()

        if search_in == "title" or search_in == "all":
            if query_lower in title_lower:
                match = True
        # Solo buscar en categoría si no hubo match en título (si search_in es 'all')
        # o si search_in es específicamente 'category'
        if not match and (search_in == "category" or search_in == "all"):
            if query_lower in category_lower:
                match = True

        if match:
            # Validar el libro antes de añadirlo a resultados
            try:
                results.append(Book(**book))
            except Exception as e:
                logging.warning(
                    f"Libro inválido encontrado durante la búsqueda y omitido: {book}. Error: {e}"
                )

    logging.info(
        f"Búsqueda por '{query}' en '{search_in}'. Encontrados {len(results)} libros."
    )
    return results


@app.get("/headlines", response_model=List[Headline])
async def get_hacker_news_headlines():
    """
    Obtiene los titulares actuales de Hacker News en tiempo real ejecutando el scraper.
    """
    logging.info("Recibida solicitud GET /headlines. Ejecutando scrape_hacker_news.")
    try:
        # Llama a la función de scraping que ahora devuelve los datos
        headlines_data = scrape_hacker_news()  # Ejecuta el scraper en tiempo real
        if not headlines_data:
            logging.warning("scrape_hacker_news no devolvió titulares.")
            # Devolver lista vacía si el scraping falla o no devuelve nada
            return []

        logging.info(
            f"scrape_hacker_news completado. Obtenidos {len(headlines_data)} titulares."
        )
        # Validar con Pydantic antes de devolver
        validated_headlines = []
        for headline in headlines_data:
            try:
                validated_headlines.append(Headline(**headline))
            except Exception as e:
                logging.warning(
                    f"Titular inválido encontrado y omitido: {headline}. Error: {e}"
                )
        return validated_headlines
    except Exception as e:
        logging.error(
            f"Error inesperado al ejecutar scrape_hacker_news: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error interno al obtener titulares: {e}"
        )


# --- Ejecución del servidor (para desarrollo) ---
# Se ejecutará con: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn

    # Nota: --reload es útil para desarrollo, pero no uses __main__ para producción.
    # Usa un gestor de procesos como Gunicorn o Uvicorn directamente.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
