from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from .config import TopicsConfig, TopicOverrides


GENERAL_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has", "have", "in", "into",
    "is", "it", "its", "of", "on", "or", "our", "that", "the", "their", "these", "this", "to", "was", "we",
    "were", "which", "with", "within", "using", "via", "than", "also", "can", "may", "between", "during",
}
ACADEMIC_STOPWORDS = {
    "result", "results", "study", "studies", "paper", "sample", "samples", "data", "analysis", "analyses", "method",
    "methods", "figure", "figures", "table", "tables", "section", "sections", "source", "sources", "object", "objects",
    "observation", "observations", "using", "based", "show", "shows", "shown", "suggest", "suggests", "find", "finds",
    "present", "work", "new", "different", "large", "number", "values", "value", "model", "models", "approach",
    "abstract", "keyword", "keywords", "introduction", "conclusion", "conclusions", "summary", "discussion", "references",
}
ASTRONOMY_LOW_INFORMATION = {
    "astronomy", "astrophysics", "stellar", "galactic", "extragalactic", "star", "stars", "galaxy", "galaxies",
    "telescope", "survey", "photometry", "spectroscopy", "variability", "evolution", "population", "populations",
}

DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "planetary nebulae": ["planetary nebula", "pn", "pne"],
    "central stars": ["central star", "central stars of planetary nebulae", "cspn", "cspne"],
    "asymptotic giant branch stars": ["asymptotic giant branch", "agb", "agb star", "agb stars"],
    "long-period variables": ["long-period variable", "lpv", "lpvs", "long period variables"],
    "mira variables": ["mira variable", "miras"],
    "M31": ["andromeda", "andromeda galaxy", "m 31"],
    "Local Group": ["local group galaxies"],
    "mass loss": ["mass-loss", "stellar mass loss"],
    "binary evolution": ["binary stellar evolution"],
    "time-series photometry": ["time series photometry", "time-domain photometry"],
    "period analysis": ["period determination", "period finding"],
    "spectral classification": ["spectroscopic classification"],
    "catalog construction": ["catalogue construction", "catalog building", "catalogue building"],
    "post-common-envelope binaries": ["post common envelope binaries", "pceb", "pcebs"],
    "emission-line objects": ["emission line objects", "emission-line sources"],
    "open clusters": ["open cluster"],
    "stellar populations": ["stellar population"],
    "pulsating variables": ["pulsating variable", "pulsating stars", "pulsators"],
    "star formation": ["star-forming", "star formation rate", "in situ star formation", "massive star formation", "in situ massive star formation"],
    "radial velocities": ["radial velocity", "rv measurements", "radial velocity monitoring", "radial velocity measurements", "velocity monitoring", "long-term radial velocity"],
    "ZTF": ["zwicky transient facility", "zwicky transient facility survey"],
    "PAndAS": ["pan-andromeda archaeological survey", "pandas survey"],
    "PHAT": ["panchromatic hubble andromeda treasury", "panchromatic hubble andromeda treasury survey"],
    "HST": ["hubble space telescope"],
    "emission-line nebulae": ["emission line nebulae", "emission-line nebula"],
    "Type II Cepheids": ["type ii cepheid", "type ii cepheid variable stars"],
    "RV Tauri variables": ["rv tauri stars", "rv tauri variable stars"],
    "post-AGB stars": ["post-agb star", "post-asymptotic giant branch stars", "post-agb stars", "post-agb binary", "binary post-agb stars"],
    "hierarchical triple systems": ["hierarchical triple", "hierarchical triple system"],
    "stellar mergers": ["stellar merger", "binary merger", "inner binary merger"],
    "spectral energy distribution fitting": ["sed fitting", "spectral energy distribution fitting"],
    "superbubbles": ["superbubble", "giant oval cavity"],
    "Perseus Arm": ["perseus arm"],
    "massive stars": ["massive star", "o-b2 stars", "o-b stars"],
    "rotation curves": ["rotation curve"],
    "mass distribution": ["mass profile", "mass distribution model"],
    "star clusters": ["star cluster", "young star clusters", "star cluster candidates"],
    "period-luminosity relation": ["period luminosity relation"],
    "PN progenitor masses": ["pn progenitor distribution", "progenitor initial mass", "pn progenitor mass", "progenitor masses", "initial mass"],
    "binary central stars": ["binary central star", "binary central systems", "confirmed binary central", "binary central stars of planetary nebulae", "bcspne"],
    "photometric variability": ["brightness variation", "brightness variations", "brightness variation observed", "periodic variability"],
}

CATEGORY_TERMS: dict[str, set[str]] = {
    "object": {
        "planetary nebulae", "central stars", "asymptotic giant branch stars", "long-period variables", "mira variables",
        "pulsating variables", "post-common-envelope binaries", "emission-line objects", "open clusters", "white dwarfs",
        "red giants", "binary stars", "variable stars", "star clusters", "supernovae", "cepheids", "rr lyrae stars",
        "emission-line nebulae", "Type II Cepheids", "RV Tauri variables", "post-AGB stars", "hierarchical triple systems",
        "circumbinary disks", "superbubbles", "massive stars", "dark matter halos",
        "binary central stars",
    },
    "physical_process": {
        "mass loss", "binary evolution", "stellar evolution", "common-envelope evolution", "pulsation", "accretion",
        "star formation", "chemical enrichment", "mass transfer", "dust formation", "nucleosynthesis", "stellar winds",
        "stellar mergers", "hot bottom burning", "binary interaction", "common-envelope evolution",
    },
    "science_question": {
        "distance scale", "period-luminosity relation", "initial-final mass relation", "formation history", "evolutionary pathways",
        "progenitor populations", "binary fraction", "metallicity distribution", "stellar ages", "population gradients",
        "rotation curves", "mass distribution", "galaxy formation", "galactic dynamics", "chemical abundances",
        "PN progenitor masses", "period-luminosity relation",
        "photometric variability",
    },
    "method": {
        "time-series photometry", "spectroscopy", "period analysis", "spectral classification", "catalog construction",
        "machine learning", "spectral energy distribution fitting", "radial velocities", "proper motions", "light-curve analysis",
        "population synthesis", "photometric calibration", "image subtraction", "cross-matching", "astrometry",
        "deep learning", "image classification", "random forest classification", "Jeans modeling",
        "spectral energy distribution fitting", "isochrone fitting", "spectral decomposition",
        "light curves", "radial velocities",
    },
    "survey_or_instrument": {
        "ZTF", "LAMOST", "Gaia", "HST", "JWST", "TESS", "Kepler", "SDSS", "DESI", "LSST", "SPHEREx",
        "Pan-STARRS", "Subaru", "VLT", "ALMA", "Chandra", "XMM-Newton", "MeerKAT", "Hubble Space Telescope",
        "PAndAS", "PHAT", "FAST",
    },
    "galaxy_or_environment": {
        "M31", "M33", "Local Group", "Milky Way", "Large Magellanic Cloud", "Small Magellanic Cloud", "galactic bulge",
        "galactic halo", "open clusters", "globular clusters", "nearby galaxies", "star-forming regions",
        "Perseus Arm", "Andromeda Giant Stellar Stream", "outer galactic disks",
    },
    "general_field": {
        "late-stage stellar evolution", "time-domain astronomy", "extragalactic stellar astrophysics", "binary evolution",
        "stellar populations", "galactic archaeology", "observational astronomy",
    },
}


def normalize_surface(text: str) -> str:
    text = text.strip().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.;:()[]{}")


class TermNormalizer:
    def __init__(self, config: TopicsConfig, overrides: TopicOverrides | None = None):
        overrides = overrides or TopicOverrides()
        synonym_map: dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_SYNONYMS.items()}
        for canonical, aliases in config.synonyms.items():
            synonym_map.setdefault(canonical, []).extend(aliases)
        for canonical, aliases in overrides.merge.items():
            synonym_map.setdefault(canonical, []).extend(aliases)

        self.alias_to_canonical: dict[str, str] = {}
        self.canonical_aliases: dict[str, set[str]] = defaultdict(set)
        for canonical, aliases in synonym_map.items():
            for form in [canonical, *aliases]:
                self.alias_to_canonical[normalize_surface(form).casefold()] = canonical
                if form.casefold() != canonical.casefold():
                    self.canonical_aliases[canonical].add(form)
        # Preserve canonical capitalization for curated instruments and named environments.
        for terms in CATEGORY_TERMS.values():
            for term in terms:
                self.alias_to_canonical.setdefault(normalize_surface(term).casefold(), term)
        self.rename = {normalize_surface(k).casefold(): v for k, v in overrides.rename.items()}
        self.excluded = {normalize_surface(x).casefold() for x in [*config.exclude, *overrides.exclude]}
        self.custom_categories = {**config.categories, **overrides.category_override}
        self.display_names = config.display_names
        self.stopwords = GENERAL_STOPWORDS | ACADEMIC_STOPWORDS | {x.casefold() for x in config.stopwords}

    def canonicalize(self, term: str) -> str:
        clean = normalize_surface(term)
        folded = clean.casefold()
        renamed = self.rename.get(folded)
        if renamed:
            clean, folded = normalize_surface(renamed), normalize_surface(renamed).casefold()
        mapped = self.alias_to_canonical.get(folded)
        if mapped is not None:
            return mapped
        canonical = clean
        if canonical.isupper() or re.fullmatch(r"M\d+", canonical):
            return canonical
        return canonical.casefold()

    def aliases_for(self, canonical: str) -> list[str]:
        return sorted(self.canonical_aliases.get(canonical, set()), key=str.casefold)

    def is_excluded(self, term: str) -> bool:
        canonical = self.canonicalize(term)
        if canonical.casefold() in self.excluded:
            return True
        words = re.findall(r"[A-Za-z0-9]+", canonical.casefold())
        if not words or all(word in self.stopwords or word in ASTRONOMY_LOW_INFORMATION for word in words):
            return True
        return len(canonical) < 3

    def category(self, term: str) -> str:
        canonical = self.canonicalize(term)
        for key, value in self.custom_categories.items():
            if self.canonicalize(key).casefold() == canonical.casefold():
                return value
        for category, terms in CATEGORY_TERMS.items():
            if any(self.canonicalize(x).casefold() == canonical.casefold() for x in terms):
                return category
        low = canonical.casefold()
        if re.search(r"\b(?:survey|telescope|instrument|observatory)\b", low) or canonical.isupper():
            return "survey_or_instrument"
        if re.search(r"\b(?:galaxy|group|cluster|cloud|bulge|halo|environment|region)s?\b", low):
            return "galaxy_or_environment"
        if re.search(r"\b(?:analysis|fitting|classification|photometry|spectroscopy|catalog|imaging|astrometry)\b", low):
            return "method"
        if re.search(r"\b(?:evolution|formation|loss|transfer|accretion|pulsation|enrichment|feedback)\b", low):
            return "physical_process"
        return "object"

    def known_forms(self) -> Iterable[tuple[str, str]]:
        return self.alias_to_canonical.items()
