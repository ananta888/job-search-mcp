"""Optionales Selenium-MVP als Vergleich zu Playwright, ohne Grid/Docker."""

from job_search_mcp.interfaces.demo_server import DemoServer


def run() -> None:
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
    except ImportError as error:
        raise RuntimeError("Installieren mit: pip install -e '.[selenium]'") from error

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    with DemoServer() as server:
        driver = webdriver.Chrome(options=options)
        try:
            driver.get(server.base_url)
            title = driver.find_element(By.TAG_NAME, "h1").text
        finally:
            driver.quit()
    print(f"Selenium: lokale Seite geöffnet -> {title}")


if __name__ == "__main__":
    run()
