from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class SearchParams(BaseModel):
    site: str = None
    col: str = None
    q: str = None
    fq: List[str] = Field(default_factory=list)
    index: str = None
    lang: str = None
    start: int = None
    sort: str = None
    rows: int = Field(None, alias='count')
    output: str = None
    tag: str = None
    fl: str = None
    fb: str = None
    facet: str = None
    facet_field: List[str] = Field(default_factory=list, alias='facet.field')
    facet_field_terms: str = Field(None, alias='facet.field.terms')

    model_config = ConfigDict(from_attributes=True, extra='allow')
