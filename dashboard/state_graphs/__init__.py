"""
Catalog of the LangGraph StateGraph pipelines in scripts/pipeline/.

Each entry is a dict naming a compiled graph (module + builder function).
Entries that also carry "summary"/"state"/"nodes" are full detail pages —
written one at a time, research_news first as the template (see
research_news.py and app.render_state_graph_page). All six are now built out.
"""
from .research_news import STATE_GRAPH as RESEARCH_NEWS
from .drug_intel import STATE_GRAPH as DRUG_INTEL
from .drug import STATE_GRAPH as DRUG
from .write_meridian import STATE_GRAPH as WRITE_MERIDIAN
from .company_intake import STATE_GRAPH as COMPANY_INTAKE
from .company_enrichment import STATE_GRAPH as COMPANY_ENRICHMENT

STATE_GRAPHS = [
    COMPANY_ENRICHMENT,
    COMPANY_INTAKE,
    DRUG,
    DRUG_INTEL,
    RESEARCH_NEWS,
    WRITE_MERIDIAN,
]
