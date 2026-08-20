import requests

url = "https://salamonimmobiliare.com/annunci/v2622-casa-singola-con-rustico-in-vendita-a-pordenone/"

response = requests.get(url)

print("prezzo" in response.text)
print("90 m²" in response.text)
print(response.text)


headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )
}

response = requests.get(url, headers=headers)

print(response.status_code)
print(response.text[:500])