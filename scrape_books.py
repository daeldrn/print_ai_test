import requests
from bs4 import BeautifulSoup
import json  # Importar json
import logging
import time

# Configuración del registro
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def scrape_books(num_books=50, price_limit=20, max_retries=3, retry_delay=1):
    """
    Extrae datos de libros de Books to Scrape (https://books.toscrape.com/)
    y guarda los resultados en un archivo JSON. # Cambiado a JSON
    Implementa la gestión de paginación, filtra por precio, lógica de reintento y registro.
    """
    base_url = "https://books.toscrape.com/catalogue/"
    books_scraped = 0
    page_num = 1
    all_books_data = []  # Lista para almacenar los datos de los libros

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    while books_scraped < num_books:
        url = f"{base_url}page-{page_num}.html"

        for attempt in range(max_retries):  # Corregida la indentación aquí
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser")
                    books = soup.find_all("article", class_="product_pod")

                    if not books:
                        logging.info("No se encontraron más libros en la página.")
                        break

                    for book in books:
                        title = book.h3.a["title"]
                        price_str = book.find("p", class_="price_color").text.strip()
                        price = float(price_str.replace("£", ""))

                        if price < price_limit:
                            image_url = base_url + book.img["src"]

                            # Extraer la categoría (asumiendo que está en la URL del libro)
                            book_url = base_url + book.h3.a["href"]

                            category = None
                            for cat_attempt in range(max_retries):
                                try:
                                    book_response = requests.get(
                                        book_url, headers=headers
                                    )
                                    book_soup = BeautifulSoup(
                                        book_response.content, "html.parser"
                                    )
                                    category = (
                                        book_soup.find("ul", class_="breadcrumb")
                                        .find_all("a")[2]
                                        .text.strip()
                                    )
                                    break  # Si tiene éxito, sale del bucle de reintentos de categoría
                                except (
                                    requests.exceptions.ConnectionError,
                                    AttributeError,
                                ) as e:
                                    logging.warning(
                                        f"Intento {cat_attempt + 1} fallido al obtener la categoría: {e}"
                                    )
                                    time.sleep(retry_delay)
                            else:
                                logging.error(
                                    f"No se pudo obtener la categoría después de {max_retries} intentos para {book_url}"
                                )
                                continue  # Si falla la categoría, continua con el siguiente libro

                            # Añadir datos a la lista como diccionario
                            all_books_data.append(
                                {
                                    "Título": title,
                                    "Precio": price,
                                    "Categoría": category,
                                    "URL de la imagen": image_url,
                                }
                            )
                            books_scraped += 1

                            if books_scraped >= num_books:
                                break

                    else:  # Corregida la indentación aquí
                        break  # Si no hay libros en la página, sale del bucle de intentos

                    break  # Si la página se procesa correctamente, sale del bucle de reintentos
                else:  # Corregida la indentación aquí
                    logging.warning(
                        f"Error al acceder a la página {url}: {response.status_code}. Intento {attempt + 1}/{max_retries}"
                    )
            except (
                requests.exceptions.RequestException
            ) as e:  # Corregida la indentación aquí
                logging.error(
                    f"Error de solicitud al acceder a {url}: {e}. Intento {attempt + 1}/{max_retries}"
                )
            time.sleep(
                retry_delay
            )  # Espera antes de reintentar # Corregida la indentación aquí
        else:  # Corregida la indentación aquí
            logging.error(
                f"No se pudo acceder a la página {url} después de {max_retries} intentos."
            )
            break  # Si no se puede acceder a la página después de varios intentos, sale del bucle de paginación

        page_num += 1  # Corregida la indentación aquí

    # Guardar los datos en un archivo JSON al final
    output_file = "books.json"
    try:
        with open(output_file, "w", encoding="utf-8") as jsonfile:
            json.dump(all_books_data, jsonfile, ensure_ascii=False, indent=4)
        logging.info(
            f"Se extrajeron {books_scraped} libros y se guardaron en {output_file}"
        )
    except IOError as e:
        logging.error(f"Error al escribir en el archivo JSON {output_file}: {e}")


if __name__ == "__main__":
    scrape_books(num_books=100)
