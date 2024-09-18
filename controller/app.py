from http import HTTPStatus
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, Response
from typing import Annotated
from decode_decs import DecodDeCS
from loguru import logger

import re
import requests
import sentry_sdk
import json
import sys
import os

# Configure log and monitoring service
logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL"))
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE",0)),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE",0)),
)

app = FastAPI()

# Configuration parameters from .env file
DEFAULT_SERVER = os.getenv("DEFAULT_SOLR_SERVER", "localhost")
DEFAULT_PORT = os.getenv("DEFAULT_SOLR_PORT", "8983")
ENCODE_REGEX = re.compile(r"\^[ds]\d+")

# Initialize DeCS decoder
decs = DecodDeCS()


def set_solr_server(site, col):
    solr = f"/{site}"
    if col:
        solr += f"-{col}"

    # Normalize site to environment variable names. ex: solr/portal -> SOLR_PORTAL
    site_env_name = site.replace("/", "_").upper()

    server = os.getenv(site_env_name, DEFAULT_SERVER)
    solr_server = f"http://{server}"

    if ":" not in server:
        solr_server += f":{DEFAULT_PORT}"

    solr_server += solr
    logger.info(f"Solr server: {solr_server}")
    return solr_server

def send_post_command(query_map, url):
    try:
        response = requests.post(url, data=query_map)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error sending POST command: {e}")
        return '"connection_problem"'

def format_query(query_string):
    replacement = "__replacement__"
    pattern = re.compile(r'["["].*?["["]')
    query_formatted = pattern.sub(replacement, query_string)

    query_formatted = query_formatted.lower()
    query_formatted = query_formatted.replace("$", "*")
    query_formatted = re.sub(r"\b(or|and not|and|to)\b", lambda m: m.group(1).upper(), query_formatted)

    for match in pattern.finditer(query_string):
        query_formatted = query_formatted.replace(replacement, match.group(0), 1)

    return query_formatted

@app.post('/search')
def search(
    site: Annotated[str, Form()],
    col: Annotated[str, Form()] = None,
    q: Annotated[str, Form()] = None,
    fq: Annotated[str, Form()] = None,
    index: Annotated[str, Form()] = None,
    lang: Annotated[str, Form()] = None,
    start: Annotated[int, Form()] = None,
    sort: Annotated[str, Form()] = None,
    count: Annotated[int, Form()] = None,
    output: Annotated[str, Form()] = None,
    tag: Annotated[str, Form()] = None,
    decode: Annotated[str, Form()] = None,
    fl: Annotated[str, Form()] = None,
    fb: Annotated[str, Form()] = None,
    facet_field: Annotated[list[str], Form(alias='facet.field')] = None,
    facet_field_terms: Annotated[str, Form(alias='facet.field.terms')] = None
):

    solr_server = set_solr_server(site, col)
    search_url = f"{solr_server}/select/"
    query_map = {}

    # Form query
    if q:
        query_formatted = format_query(q)
        query_map['q'] = f"{index}:({query_formatted})" if index else query_formatted
    else:
        query_map['q'] = "*:*"
        query_map['facet.method'] = "enum"

    if fq:
        query_map['fq'] = format_query(fq)

    # Add other parameters to query_map
    for param in ['start', 'sort', 'count', 'tag', 'fl']:
        value = locals()[param]
        if value:
            query_map[param] = value

    if output == "xml":
        query_map['wt'] = "xslt"
        query_map['tr'] = "export-xml.xsl"
    elif output != "solr":
        query_map['wt'] = "json"
        query_map['json.nl'] = "arrarr"

    if fb:
        fb_param = fb.split(':')
        query_map[f"f.{fb_param[0]}.facet.limit"] = fb_param[1]

    if facet_field:
        query_map['facet.field'] = facet_field

    # Used for restrict the count of a facet to fixed list of options (ex. used in tab implementation)
    if facet_field_terms:
        facet_field_terms_parts = facet_field_terms.split(':')
        facet_field_name = facet_field_terms_parts[0]
        facet_field_terms = facet_field_terms_parts[1]

        query_map['facet.field'] = "{{!terms={}}}{}".format(facet_field_terms, facet_field_name)

    result = send_post_command(query_map, search_url)

    if decode == 'true' and ENCODE_REGEX.search(result):
        logger.info(f"Applying decod for language {lang}")
        result = decs.decode(result, lang)

        # Remove subfields marks of non decoded descriptors
        result = re.sub(r"(\^d)", "", result)
        result = re.sub(r"\^s(\w*)/*", r"/\1", result)

    if output in ['xml', 'solr']:
        return Response(content=result, media_type="text/xml; charset=utf-8", headers={"Cache-Control": "no-cache"})
    else:
        result = '{"diaServerResponse":[' + result + ']}';
        return JSONResponse(content=json.loads(result), headers={"Cache-Control": "no-cache"})

