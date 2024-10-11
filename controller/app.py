from http import HTTPStatus
from fastapi import FastAPI, Header, HTTPException, Request, Form
from fastapi.responses import JSONResponse, Response
from typing import Annotated, List
from decode_decs import DecodDeCS
from contextlib import asynccontextmanager
from loguru import logger

import re
import httpx
import random
import sentry_sdk
import json
import sys
import os

# Configure log and monitoring service
logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL"), serialize=False)
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE",0)),
    profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE",0)),
)


# Configuration parameters from .env file
DEFAULT_SERVER = os.getenv("DEFAULT_SOLR_SERVER", "localhost")
DEFAULT_PORT = os.getenv("DEFAULT_SOLR_PORT", "8983")
API_TOKEN = os.getenv("API_TOKEN", "8983")
ENCODE_REGEX = re.compile(r"\^[ds]\d+")
SOLR_TIMEOUT = int(os.getenv("SOLR_TIMEOUT", 10))

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient()
    app.state.decs = DecodDeCS()  # Initialize DeCS decoder
    yield
    await app.state.client.aclose()
    await app.state.decs.close()


app = FastAPI(lifespan=lifespan)

def set_solr_server(site, col):
    solr = f"/{site}"
    if col:
        solr += f"-{col}"

    # Normalize site to environment variable names. ex: solr/portal -> SOLR_PORTAL
    site_env_name = site.replace("/", "_").replace("-","_").upper()

    server = os.getenv(site_env_name, DEFAULT_SERVER)

    # If server is a list
    if ',' in server:
        # Split the string by commas and strip any leading/trailing spaces
        server_list = [s.strip() for s in server.split(",")]

        # Randomly select one of the servers
        server = random.choice(server_list)

    solr_server = f"http://{server}"

    if ":" not in server:
        solr_server += f":{DEFAULT_PORT}"

    solr_server += solr
    logger.info(f"Solr server: {solr_server}")
    return solr_server

async def send_post_command(query_map, url):
    logger.info(query_map)

    try:
        response = await app.state.client.post(url, data=query_map, timeout=SOLR_TIMEOUT)
        response.raise_for_status()
        return response.text
    except httpx.RequestError as e:
        logger.error(f"Error sending POST command: {e}")
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid POST or connection error with Solr server"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Error response from Solr server"
        )

def fix_double_quotes(input_string):
    # Replace curly double quotes with standard double quotes
    input_string = input_string.replace('“', '"').replace('”', '"')

    # Check if the string starts with a double quote and does not end with one
    if input_string.count('"') % 2 != 0 and input_string.endswith('"') is False:
        return input_string + '"'

    return input_string


def format_query(query_string):
    replacement = "__replacement__"
    pattern = re.compile(r'["["].*?["["]')
    query_formatted = pattern.sub(replacement, query_string)

    query_formatted = query_formatted.lower()
    query_formatted = query_formatted.replace("$", "*")
    query_formatted = re.sub(r"\b(or|and not|and|to)\b", lambda m: m.group(1).upper(), query_formatted)

    for match in pattern.finditer(query_string):
        query_formatted = query_formatted.replace(replacement, match.group(0), 1)

    # Fix common doble quotes errors at query string
    query_formatted = fix_double_quotes(query_formatted)

    return query_formatted

@app.post('/search')
async def search(
    site: Annotated[str, Form()],
    col: Annotated[str, Form()] = None,
    q: Annotated[str, Form()] = None,
    fq: Annotated[str, Form()] = None,
    index: Annotated[str, Form()] = None,
    lang: Annotated[str, Form()] = None,
    start: Annotated[int, Form()] = None,
    sort: Annotated[str, Form()] = None,
    rows: Annotated[int, Form(alias='count')] = None,
    output: Annotated[str, Form()] = None,
    tag: Annotated[str, Form()] = None,
    fl: Annotated[str, Form()] = None,
    fb: Annotated[str, Form()] = None,
    facet: Annotated[str, Form()] = None,
    facet_field: List[str] = Form(default_factory=list, alias='facet.field'),
    facet_field_terms: Annotated[str, Form(alias='facet.field.terms')] = None,
    apikey: str = Header(...),
):

    if apikey != API_TOKEN:
        raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail='Invalid api key',
        )

    solr_server = set_solr_server(site, col)
    search_url = f"{solr_server}/select/"
    query_map = {}

    # Form query
    if q:
        query_formatted = format_query(q)
        query_map['q'] = f"{index}:({query_formatted})" if index else query_formatted
    else:
        query_map['q'] = "*:*"

    if fq:
        query_map['fq'] = format_query(fq)

    # Add other parameters to query_map
    for param in ['start', 'sort', 'rows', 'tag', 'fl', 'facet']:
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


    # Used for restrict the count of a facet to fixed list of options (ex. used in tab implementation)
    if facet_field_terms:
        facet_field_terms_parts = facet_field_terms.split(':')
        facet_field_name = facet_field_terms_parts[0]
        facet_field_terms = facet_field_terms_parts[1]

        # https://solr.apache.org/guide/6_6/faceting.html#Faceting-TaggingandExcludingFilters
        facet_field.append("{{!ex=tab terms={}}}{}".format(facet_field_terms, facet_field_name))

    if facet_field:
        query_map['facet.field'] = facet_field

    result = await send_post_command(query_map, search_url)

    # Run regular expression and decode if found thesaurus codes
    if ENCODE_REGEX.search(result):
        logger.info(f"Applying decod for language {lang}")
        result = app.state.decs.decode(result, lang)

        # Remove subfields marks of non decoded descriptors
        result = re.sub(r"(\^d)", "", result)
        result = re.sub(r"\^s(\w*)/*", r"/\1", result)

    if output in ['xml', 'solr']:
        return Response(content=result, media_type="text/xml; charset=utf-8", headers={"Cache-Control": "no-cache"})
    else:
        result = '{"diaServerResponse":[' + result + ']}';
        return JSONResponse(content=json.loads(result), headers={"Cache-Control": "no-cache"})


@app.get('/healthcheck')
async def healthcheck(
    apikey: str = Header(...),
):
    if apikey != API_TOKEN:
        raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail='Invalid api key',
        )

    lang = 'en'
    solr_server = set_solr_server("solr5/portal", None)
    search_url = f"{solr_server}/select/"
    query_map = {
        'q': "malaria",
        'rows': 1,
        'facet': "false",
        'wt': "json",
        'json.nl': "arrarr"
    }

    result = await send_post_command(query_map, search_url)
    result = app.state.decs.decode(result, lang)

    return JSONResponse(content=json.loads(result), headers={"Cache-Control": "no-cache"})
