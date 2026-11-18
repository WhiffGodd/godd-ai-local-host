"""Retrieve photographic assets with source and attribution metadata."""

from html import unescape
from io import BytesIO
import re
from urllib.parse import urlsplit

from PIL import Image
import requests


def _plain(value):
    return " ".join(unescape(re.sub(r"<[^>]*>"," ",value)).split())


def photo_credit(page, info):
    metadata = info.get("extmetadata") or {}
    def value(key):
        return _plain(metadata.get(key,{}).get("value",""))
    license_url = value("LicenseUrl").replace("http://","https://")
    parsed = urlsplit(license_url)
    public_domain = value("Copyrighted").casefold() == "false"
    cc_by = parsed.hostname == "creativecommons.org" and parsed.path.startswith("/licenses/by/")
    cc0 = parsed.hostname == "creativecommons.org" and parsed.path.startswith("/publicdomain/")
    if not (public_domain or cc_by or cc0):
        return None
    source = info.get("descriptionurl","")
    if urlsplit(source).hostname != "commons.wikimedia.org":
        return None
    title = page["title"].removeprefix("File:")
    author = value("Artist") or value("Attribution") or "Wikimedia Commons contributor"
    license_name = value("LicenseShortName") or "Public domain"
    attribution = value("Attribution")
    notice = value("Credit")
    details = f"{title} — {author}. {license_name}"
    if attribution and attribution.casefold() not in details.casefold():
        details += ". "+attribution
    if notice and len(notice)<220 and notice.casefold() not in details.casefold():
        details += ". "+notice
    return details+f". Cropped, background removed and animated.\n{source}"+(
        "\n"+license_url if license_url else "")


def find_photo(query):
    """Return a photo and its credit, or let the caller generate an asset locally."""
    query = re.sub(r"[^\w\s-]"," ",query.replace("_"," "))[:100].strip()
    if not query:
        return None
    headers = {"User-Agent":"GoddAI/1.0 (educational explainer photo lookup; https://github.com/WhiffGodd/godd-ai)"}
    params = {"action":"query","format":"json","generator":"search","gsrnamespace":6,
              "gsrlimit":16,"prop":"imageinfo",
              "iiprop":"url|extmetadata|mime|size","iiurlwidth":800}
    try:
        pages = ()
        for license_template in ("cc-by-2.0","cc-by-4.0","cc-zero"):
            params["gsrsearch"] = query+" filetype:bitmap hastemplate:"+license_template
            response = requests.get("https://commons.wikimedia.org/w/api.php",params=params,headers=headers,timeout=15)
            response.raise_for_status()
            pages = response.json().get("query",{}).get("pages",{}).values()
            if pages:
                break
        candidates = []
        query_words = set(re.findall(r"\w+",query.casefold()))
        for page in pages:
            info = next(iter(page.get("imageinfo",[])),{})
            credit = photo_credit(page,info)
            if credit and info.get("mime") in ("image/jpeg","image/png","image/webp"):
                words = set(re.findall(r"[a-z]+",page["title"].removeprefix("File:").casefold()))
                score = len(words)-10*len(query_words&words)+page.get("index",1000)/100
                candidates.append((score,info,credit))
        for _,info,credit in sorted(candidates,key=lambda candidate:candidate[0])[:3]:
            url = info.get("thumburl") or info.get("url","")
            if urlsplit(url).hostname not in ("upload.wikimedia.org","thumb.wikimedia.org"):
                continue
            with requests.get(url,headers=headers,stream=True,timeout=20) as download:
                download.raise_for_status()
                content = bytearray()
                for chunk in download.iter_content(65536):
                    content.extend(chunk)
                    if len(content)>12*1024*1024:
                        break
            if len(content)>12*1024*1024:
                continue
            with Image.open(BytesIO(content)) as image:
                image.thumbnail((1024,1024),Image.Resampling.LANCZOS)
                from motion_graphics import extract_cutout
                from explainer_visuals import VisualUnavailable
                try:
                    return extract_cutout(image.convert("RGB")),credit
                except VisualUnavailable:
                    continue
    except (requests.RequestException,ValueError,KeyError,TypeError,OSError):
        return None
    return None
