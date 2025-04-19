import json
import logging  # Importar logging
import time
from selenium import webdriver
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)  # Importar excepciones específicas
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Configuración del registro
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constantes para reintentos
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos


def scrape_hacker_news(output_file="hacker_news.json"):
    """
    Scrapes the top news from Hacker News (https://news.ycombinator.com/)
    and saves the title, score, and URL to a JSON file.
    Includes retry logic, logging, and graceful failure handling.
    """
    logging.info("Iniciando el scraping de Hacker News...")

    # Configuración de opciones de Chrome para modo headless
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument(
        "--window-size=1920x1080"
    )  # Puede ayudar en modo headless
    chrome_options.add_argument(
        "--no-sandbox"
    )  # Necesario en algunos entornos Linux/Docker
    chrome_options.add_argument(
        "--disable-dev-shm-usage"
    )  # Necesario en algunos entornos Linux/Docker

    driver = None
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(
                f"Intento {attempt + 1}/{MAX_RETRIES} para iniciar WebDriver..."
            )
            # Configurar el servicio de ChromeDriver usando webdriver-manager
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logging.info("WebDriver iniciado correctamente.")
            break  # Salir del bucle si tiene éxito
        except WebDriverException as e:
            logging.warning(
                f"Error al iniciar WebDriver (Intento {attempt + 1}/{MAX_RETRIES}): {e}"
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logging.error(
                    "No se pudo iniciar WebDriver después de varios intentos."
                )
                return []  # Salir de la función si no se puede iniciar el driver

    if not driver:
        return []  # Salir si el driver no se inicializó

    try:
        # Navegar a Hacker News con reintentos
        hn_url = "https://news.ycombinator.com/"
        for attempt in range(MAX_RETRIES):
            try:
                logging.info(
                    f"Intento {attempt + 1}/{MAX_RETRIES} para navegar a {hn_url}"
                )
                driver.get(hn_url)
                # Podríamos añadir una espera explícita aquí si fuera necesario
                # WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.athing")))
                logging.info(f"Navegación a {driver.current_url} exitosa.")
                time.sleep(RETRY_DELAY)  # Dar tiempo a que cargue JS si es necesario
                break
            except (WebDriverException, TimeoutException) as e:
                logging.warning(
                    f"Error al navegar a {hn_url} (Intento {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    logging.error(
                        f"No se pudo cargar la página {hn_url} después de varios intentos."
                    )
                    if driver:
                        driver.quit()  # Asegurarse de cerrar el driver
                    return []  # Salir si no se puede cargar la página

        news_items = []
        rows = []
        # Encontrar elementos con reintentos
        for attempt in range(MAX_RETRIES):
            try:
                logging.info(
                    f"Intento {attempt + 1}/{MAX_RETRIES} para encontrar elementos de noticias."
                )
                rows = driver.find_elements(By.CSS_SELECTOR, "tr.athing")
                if rows:
                    logging.info(f"Encontrados {len(rows)} elementos de noticias.")
                    break
                else:
                    logging.warning(
                        "No se encontraron elementos de noticias, reintentando..."
                    )
                    time.sleep(RETRY_DELAY)
            except NoSuchElementException:
                logging.warning(
                    f"No se encontraron elementos 'tr.athing' (Intento {attempt + 1}/{MAX_RETRIES})."
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    logging.error(
                        "No se pudieron encontrar elementos de noticias después de varios intentos."
                    )
                    if driver:
                        driver.quit()  # Asegurarse de cerrar el driver
                    return []  # Salir si no se encuentran elementos

        if not rows:
            logging.warning(
                "No se procesaron noticias porque no se encontraron elementos."
            )
            if driver:
                driver.quit()  # Asegurarse de cerrar el driver
            return []

        for i, row in enumerate(rows):
            title = "N/A"
            url = "N/A"
            score = 0
            try:
                # Extraer título y URL
                title_element = row.find_element(
                    By.CSS_SELECTOR, "td.title > span.titleline > a"
                )
                title = title_element.text
                url = title_element.get_attribute("href")

                # Extraer puntuación (en la siguiente fila)
                subtext_row = row.find_element(By.XPATH, "./following-sibling::tr")
                try:
                    score_element = subtext_row.find_element(
                        By.CSS_SELECTOR, "span.score"
                    )
                    score_text = score_element.text.split()[0]
                    score = int(score_text)
                except NoSuchElementException:
                    logging.debug(
                        f"No se encontró puntuación para el item {i + 1}: {title[:30]}..."
                    )  # Menos verboso
                except (ValueError, IndexError):
                    logging.warning(
                        f"Error al parsear la puntuación para el item {i + 1}: {title[:30]}..."
                    )

                news_items.append({"title": title, "score": score, "url": url})
                logging.info(
                    f"Procesado item {i + 1}/{len(rows)}: {title[:50]}... (Score: {score})"
                )

            except NoSuchElementException as e:
                logging.warning(
                    f"Error al procesar el item {i + 1}: No se encontró un elemento esperado ({e}). Saltando item."
                )
            except Exception as e:
                logging.error(
                    f"Error inesperado al procesar el item {i + 1} ('{title[:30]}...'): {e}"
                )

        # Guardar los datos en un archivo JSON
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(news_items, f, ensure_ascii=False, indent=4)
            logging.info(
                f"Scraping completado. {len(news_items)} noticias guardadas en {output_file}"
            )
            return news_items  # Devolver los items
        except IOError as e:
            logging.error(f"Error al escribir en el archivo JSON {output_file}: {e}")
            return news_items  # Devolver los items aunque falle la escritura

    except Exception as e:
        logging.error(
            f"Ocurrió un error general durante el scraping: {e}", exc_info=True
        )  # Añadir traceback
        return []  # Devolver lista vacía en caso de error general
    finally:
        # Asegurarse de cerrar el driver
        if driver:
            driver.quit()
            logging.info("WebDriver cerrado.")


if __name__ == "__main__":
    headlines = scrape_hacker_news()
    if headlines:
        print(f"Se obtuvieron {len(headlines)} titulares.")
    else:
        print("No se pudieron obtener los titulares.")
