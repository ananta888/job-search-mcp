"""Laden und validieren des lokalen Unterrichtsprofils."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from job_search_mcp.paths import LOCAL_DEMO_PROFILE

PROFILE_PATH = LOCAL_DEMO_PROFILE


class SelectorProfile(BaseModel):
    input_label: str
    submit_role: Literal["button"] = "button"
    submit_name: str
    output_css: str


class PolicyProfile(BaseModel):
    allowed_hosts: list[str] = Field(min_length=1)
    allowed_paths: list[str] = Field(min_length=1)


class ValidationProfile(BaseModel):
    schema_file: str
    ignore_paths: list[str] = Field(default_factory=list)


class TeachingProfile(BaseModel):
    name: str
    base_url: str
    selectors: SelectorProfile
    policy: PolicyProfile
    validation: ValidationProfile


def read_profile_yaml(path: Path = PROFILE_PATH) -> dict[str, object]:
    """Read YAML without silently accepting a non-mapping document."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Profil muss ein YAML-Mapping sein: {path}")
    return raw


def load_profile(path: Path = PROFILE_PATH) -> TeachingProfile:
    return TeachingProfile.model_validate(read_profile_yaml(path))
