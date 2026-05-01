#!/usr/bin/env python3
"""
System/alphafold_compliance.py

Machine-readable AlphaFold policy metadata for SIFTA folding receipts.

This is not legal advice. It encodes the public distinction SIFTA must preserve:

* AlphaFold Protein Structure Database (AFDB) structures are public database
  records available under CC-BY-4.0 with attribution.
* AlphaFold Server / AlphaFold 3 outputs are a separate surface with
  non-commercial and downstream-use restrictions.

SIFTA receipts should carry the policy that matches the actual artifact source.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional


AFDB_LICENSE_POLICY: Dict[str, Any] = {
    "policy_id": "alphafold_db_cc_by_4_0_attribution_v1",
    "artifact_family": "AlphaFold Protein Structure Database",
    "allowed_use": "academic_and_commercial_with_attribution",
    "license": "CC-BY-4.0",
    "requires_attribution": True,
    "requires_terms_notice": False,
    "terms_url": "https://alphafold.ebi.ac.uk/",
    "license_url": "https://alphafold.ebi.ac.uk/assets/License-Disclaimer.pdf",
    "attribution": {
        "database": "AlphaFold Protein Structure Database",
        "providers": ["Google DeepMind", "EMBL-EBI"],
        "copyright": "AlphaFold Data Copyright DeepMind Technologies Limited",
    },
    "citations": [
        {
            "id": "jumper_2021_alphafold",
            "text": "Jumper J. et al. Highly accurate protein structure prediction with AlphaFold. Nature 596, 583-589 (2021).",
            "doi": "10.1038/s41586-021-03819-2",
        },
        {
            "id": "fleming_2025_afdb_3d_beacons",
            "text": "Fleming J. et al. AlphaFold Protein Structure Database and 3D-Beacons: New Data and Capabilities. Journal of Molecular Biology (2025).",
            "doi": "10.1016/j.jmb.2025.168935",
        },
    ],
    "disclaimer": "Theoretical modelling only; not a substitute for professional medical advice.",
}


ALPHAFOLD_SERVER_OUTPUT_POLICY: Dict[str, Any] = {
    "policy_id": "alphafold_server_output_terms_2024_05_08_v1",
    "artifact_family": "AlphaFold Server / AlphaFold 3 output",
    "allowed_use": "non_commercial_only",
    "license": "AlphaFold Server Output Terms of Use",
    "requires_attribution": True,
    "requires_terms_notice": True,
    "terms_url": "https://alphafoldserver.com/output-terms",
    "additional_terms_pdf": "https://www.gstatic.com/alphafoldserver/app/app/routes/terms_text/AlphaFold-Server-Additional-Terms-of-Service.pdf",
    "output_terms_pdf": "https://www.gstatic.com/alphafoldserver/app/app/routes/terms_output/AlphaFold-Server-Output-Terms-of-Use.pdf",
    "required_notice": "This information is subject to AlphaFold Server Output Terms of Use found at alphafoldserver.com/output-terms.",
    "prohibited_uses": [
        "commercial_activity_or_research_on_behalf_of_commercial_organization",
        "automated_binding_or_interaction_prediction_systems_including_glide_or_autodock",
        "training_biomolecular_structure_prediction_models_or_related_technology_similar_to_alphafold",
        "misrepresentation_of_origin_or_google_endorsement",
        "clinical_or_medical_decision_use",
        "dangerous_illegal_or_malicious_activity",
    ],
    "citations": [
        {
            "id": "abramson_2024_alphafold3",
            "text": "Abramson J. et al. Accurate structure prediction of biomolecular interactions with AlphaFold 3. Nature (2024).",
            "doi": "10.1038/s41586-024-07487-w",
        }
    ],
    "disclaimer": "Theoretical modelling only; not clinical, medical, or professional advice.",
}


def policy_for_artifact_family(artifact_family: str) -> Dict[str, Any]:
    """Return a defensive copy of the policy for a known AlphaFold surface."""

    normalized = artifact_family.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"afdb", "alphafold_db", "alphafold_protein_structure_database"}:
        return deepcopy(AFDB_LICENSE_POLICY)
    if normalized in {"alphafold_server", "alphafold3_server", "alphafold_server_output"}:
        return deepcopy(ALPHAFOLD_SERVER_OUTPUT_POLICY)
    raise ValueError(f"unknown AlphaFold artifact family: {artifact_family!r}")


def alphafold_db_compliance_metadata(
    *,
    uniprot_id: str,
    source_url: str,
    version: Any,
    gene: str = "",
    organism: str = "",
) -> Dict[str, Any]:
    """Build AFDB attribution block for one downloaded database structure."""

    policy = policy_for_artifact_family("alphafold_db")
    return {
        "artifact_family": policy["artifact_family"],
        "policy_id": policy["policy_id"],
        "uniprot_id": str(uniprot_id).upper(),
        "source_url": str(source_url),
        "afdb_version": str(version),
        "gene": str(gene or ""),
        "organism": str(organism or ""),
        "license": policy["license"],
        "allowed_use": policy["allowed_use"],
        "requires_attribution": policy["requires_attribution"],
        "license_url": policy["license_url"],
        "terms_url": policy["terms_url"],
        "attribution": deepcopy(policy["attribution"]),
        "citations": deepcopy(policy["citations"]),
        "disclaimer": policy["disclaimer"],
    }


def alphafold_server_output_policy_metadata(
    *,
    output_generated_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Build policy block for AlphaFold Server outputs, without claiming one exists."""

    policy = policy_for_artifact_family("alphafold_server")
    payload = deepcopy(policy)
    if output_generated_date:
        payload["output_generated_date"] = str(output_generated_date)
    return payload

