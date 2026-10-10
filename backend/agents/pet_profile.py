"""Pet Profile Extraction Agent: builds a structured PetProfile from the saved pet plus the message."""
import re
import time
from typing import Any, Dict, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from llm import get_llm, llm_available
from state import PetCareState, make_trace
from tools.text_parsing import extract_constraints, extract_pet_fields

UPDATE_SIGNAL = re.compile(r"\b(now|weighs|weighing|is now|just turned|turned|updated?)\b", re.I)
PROFILE_KEYS = ("name", "species", "breed", "age", "weight_kg", "activity_level")


class PetProfile(BaseModel):
    """Structured pet profile. This is your TripRequest schema, re-purposed for pets."""
    name: Optional[str] = Field(None, description="The pet's name")
    species: Optional[str] = Field(None, description="dog, cat, rabbit, bird, hamster, guinea pig or other")
    breed: Optional[str] = Field(None, description="Breed if mentioned")
    age: Optional[float] = Field(None, description="Age in years", ge=0)
    weight_kg: Optional[float] = Field(None, description="Weight in kilograms", gt=0)
    activity_level: Optional[str] = Field(None, description="low, moderate or high")


def build_extraction_chain():
    """LCEL chain: prompt | llm | parser (same pattern as your Phase 3 extraction chain)."""
    parser = JsonOutputParser(pydantic_object=PetProfile)
    prompt = PromptTemplate(
        template=(
            "Extract the pet details from the owner's message below and return them as JSON. "
            "Leave out anything that is not mentioned.\n{format_instructions}\n\n"
            "Owner message: \"{request}\"\n"
        ),
        input_variables=["request"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    return prompt | get_llm() | parser


def _llm_profile(msg: str) -> Dict[str, Any]:
    """Model-based extraction, used only when the rules found no species. Returns {} if the model is unavailable."""
    if not llm_available():
        return {}
    try:
        data = build_extraction_chain().invoke({"request": msg})
        profile = PetProfile(**{k: v for k, v in data.items() if v not in (None, "", "unknown")})
    except Exception:
        return {}
    return {k: v for k, v in profile.model_dump().items() if v is not None}


def pet_profile_node(state: PetCareState):
    t = time.time()
    msg = state.get("user_message", "")
    pet: Dict[str, Any] = dict(state.get("pet") or {})
    found = extract_pet_fields(msg)
    updates: Dict[str, Any] = {}

    if pet:
        # Only treat numbers in the message as updates when the user signals a change.
        if UPDATE_SIGNAL.search(msg):
            for k in ("weight_kg", "age"):
                if k in found and found[k] != pet.get(k):
                    updates[k] = found[k]
            pet.update(updates)
        source = "saved profile"
    else:
        pet = {k: v for k, v in found.items() if k in PROFILE_KEYS}
        if "species" not in pet:
            pet.update({k: v for k, v in _llm_profile(msg).items() if k not in pet})
        pet.setdefault("activity_level", "moderate")
        source = "message text"

    constraints = extract_constraints(msg)
    name = pet.get("name") or "your pet"
    bits = [str(pet.get(k)) for k in ("name", "breed", "species") if pet.get(k)]
    summary = f"{' / '.join(bits) or 'No pet details found'} (from {source})"
    if updates:
        summary += f"; updated {', '.join(updates)}"
    if constraints["unavailable_days"]:
        summary += f"; away {', '.join(constraints['unavailable_days'])}"

    return {
        "profile": pet,
        "profile_updates": updates,
        "constraints": constraints,
        "trace": [make_trace("Pet Profile Extraction Agent", summary, t, pet=name)],
    }
