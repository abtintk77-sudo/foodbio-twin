#!/usr/bin/env python3
"""FoodBio-Twin: illustrative digital-twin risk scoring prototype.

This is a transparent teaching/demo model using synthetic or user-supplied CSV
records. It is not a validated epidemiological model and does not predict a
probability of infection or contamination.
"""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = (
    "batch_id",
    "date",
    "site_id",
    "visitor_count",
    "biosecurity_compliance_pct",
    "wildlife_contact_index",
    "mortality_change_pct",
    "ventilation_stress_index",
    "lab_indicator_index",
    "cooling_delay_min",
    "cold_chain_excursion_min",
    "sanitation_failure_index",
)

# Illustrative weights only. Replace and recalibrate with expert-reviewed data.
DISEASE_WEIGHTS = {
    "biosecurity_gap": 0.28,
    "visitor_pressure": 0.18,
    "wildlife_contact": 0.20,
    "mortality_signal": 0.20,
    "ventilation_stress": 0.14,
}
FOOD_SAFETY_WEIGHTS = {
    "lab_indicator": 0.35,
    "cooling_delay": 0.25,
    "cold_chain_excursion": 0.20,
    "sanitation_failure": 0.20,
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def as_float(row: dict[str, Any], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field}' must be numeric; got {row.get(field)!r}") from exc
    return value


def validate_record(row: dict[str, Any], line_number: int = 0) -> dict[str, Any]:
    """Validate a CSV row and return a typed copy."""
    missing = [field for field in REQUIRED_COLUMNS if field not in row or row[field] == ""]
    if missing:
        raise ValueError(f"Row {line_number}: missing required fields: {', '.join(missing)}")

    parsed: dict[str, Any] = {key: row[key] for key in ("batch_id", "date", "site_id")}
    numeric_fields = REQUIRED_COLUMNS[3:]
    for field in numeric_fields:
        parsed[field] = as_float(row, field)

    if parsed["visitor_count"] < 0:
        raise ValueError(f"Row {line_number}: visitor_count cannot be negative")
    for field in ("biosecurity_compliance_pct",):
        if not 0 <= parsed[field] <= 100:
            raise ValueError(f"Row {line_number}: {field} must be between 0 and 100")
    for field in ("wildlife_contact_index", "ventilation_stress_index", "lab_indicator_index", "sanitation_failure_index"):
        if not 0 <= parsed[field] <= 1:
            raise ValueError(f"Row {line_number}: {field} must be between 0 and 1")
    for field in ("mortality_change_pct", "cooling_delay_min", "cold_chain_excursion_min"):
        if parsed[field] < 0:
            raise ValueError(f"Row {line_number}: {field} cannot be negative")

    return parsed


def score_components(record: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
    """Return normalized explanatory factors for both risk indices."""
    disease = {
        "biosecurity_gap": 1.0 - record["biosecurity_compliance_pct"] / 100.0,
        "visitor_pressure": clamp(record["visitor_count"] / 10.0),
        "wildlife_contact": clamp(record["wildlife_contact_index"]),
        "mortality_signal": clamp(record["mortality_change_pct"] / 8.0),
        "ventilation_stress": clamp(record["ventilation_stress_index"]),
    }
    food = {
        "lab_indicator": clamp(record["lab_indicator_index"]),
        "cooling_delay": clamp(record["cooling_delay_min"] / 90.0),
        "cold_chain_excursion": clamp(record["cold_chain_excursion_min"] / 120.0),
        "sanitation_failure": clamp(record["sanitation_failure_index"]),
    }
    return disease, food


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    return round(100.0 * sum(components[key] * weights[key] for key in weights), 1)


def risk_level(score: float) -> str:
    """Demonstration categories; not validated operational thresholds."""
    if score < 30:
        return "LOW"
    if score < 60:
        return "MODERATE"
    return "HIGH"


def top_drivers(components: dict[str, float], weights: dict[str, float], limit: int = 2) -> str:
    contributions = sorted(
        ((name, components[name] * weight) for name, weight in weights.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    return "; ".join(name.replace("_", " ") for name, contribution in contributions[:limit] if contribution > 0.05) or "no dominant signal"


def assess(record: dict[str, Any]) -> dict[str, Any]:
    disease, food = score_components(record)
    disease_score = weighted_score(disease, DISEASE_WEIGHTS)
    food_score = weighted_score(food, FOOD_SAFETY_WEIGHTS)
    return {
        "batch_id": record["batch_id"],
        "date": record["date"],
        "site_id": record["site_id"],
        "disease_risk_score": disease_score,
        "disease_risk_level": risk_level(disease_score),
        "disease_top_drivers": top_drivers(disease, DISEASE_WEIGHTS),
        "food_safety_risk_score": food_score,
        "food_safety_risk_level": risk_level(food_score),
        "food_safety_top_drivers": top_drivers(food, FOOD_SAFETY_WEIGHTS),
    }


def recommendations(record: dict[str, Any]) -> list[str]:
    """Generate review prompts, not automatic control instructions."""
    prompts: list[str] = []
    if record["biosecurity_compliance_pct"] < 85:
        prompts.append("Review biosecurity checklist gaps and verify corrective actions.")
    if record["visitor_count"] >= 6:
        prompts.append("Review visitor access, logs, and hygiene/barrier procedures.")
    if record["wildlife_contact_index"] >= 0.6:
        prompts.append("Inspect wildlife exclusion and feed/water protection controls.")
    if record["mortality_change_pct"] >= 4:
        prompts.append("Check the mortality trend and escalate to the responsible veterinarian under site protocol.")
    if record["ventilation_stress_index"] >= 0.6:
        prompts.append("Review ventilation/environment alarms and document the response.")
    if record["lab_indicator_index"] >= 0.6:
        prompts.append("Review the laboratory result against the validated method and site action limits.")
    if record["cooling_delay_min"] >= 30:
        prompts.append("Investigate the cooling delay and verify the time-temperature record.")
    if record["cold_chain_excursion_min"] >= 20:
        prompts.append("Review cold-chain excursion duration and product disposition procedure.")
    if record["sanitation_failure_index"] >= 0.5:
        prompts.append("Verify sanitation corrective action and required re-checks.")
    return prompts or ["Continue routine monitoring; do not interpret this score as proof of absence of risk."]


def apply_scenario(record: dict[str, Any], scenario: str) -> dict[str, Any]:
    """Apply transparent hypothetical changes; these are not efficacy estimates."""
    simulated = deepcopy(record)
    if scenario == "biosecurity":
        simulated["biosecurity_compliance_pct"] = min(100.0, simulated["biosecurity_compliance_pct"] + 15.0)
        simulated["visitor_count"] = max(0.0, simulated["visitor_count"] - 2.0)
        simulated["wildlife_contact_index"] = max(0.0, simulated["wildlife_contact_index"] - 0.25)
    elif scenario == "processing_hygiene":
        simulated["cooling_delay_min"] *= 0.5
        simulated["cold_chain_excursion_min"] *= 0.5
        simulated["sanitation_failure_index"] = max(0.0, simulated["sanitation_failure_index"] - 0.3)
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    return simulated


def load_records(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is empty or has no header")
        missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Input CSV is missing columns: {', '.join(missing)}")
        records = [validate_record(row, index) for index, row in enumerate(reader, start=2)]
    if not records:
        raise ValueError("Input CSV contains no data rows")
    return records


def write_csv(output_path: Path, rows: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score illustrative farm biosecurity and food-safety risk indices.")
    parser.add_argument("--input", type=Path, default=Path("data/sample_batches.csv"), help="Input batch observation CSV")
    parser.add_argument("--output", type=Path, default=Path("results/risk_assessment.csv"), help="Output assessment CSV")
    parser.add_argument("--scenario", choices=("biosecurity", "processing_hygiene"), help="Run a hypothetical what-if intervention")
    args = parser.parse_args()

    try:
        records = load_records(args.input)
        output_rows: list[dict[str, Any]] = []
        for record in records:
            baseline = assess(record)
            result = dict(baseline)
            if args.scenario:
                simulated = assess(apply_scenario(record, args.scenario))
                result["scenario"] = args.scenario
                result["scenario_disease_risk_score"] = simulated["disease_risk_score"]
                result["scenario_food_safety_risk_score"] = simulated["food_safety_risk_score"]
                result["disease_score_change"] = round(simulated["disease_risk_score"] - baseline["disease_risk_score"], 1)
                result["food_safety_score_change"] = round(simulated["food_safety_risk_score"] - baseline["food_safety_risk_score"], 1)
            result["review_prompts"] = " | ".join(recommendations(record))
            output_rows.append(result)

        write_csv(args.output, output_rows)
        print(f"Assessed {len(output_rows)} records -> {args.output}")
        print("Scores are illustrative indices, not probabilities or validated action thresholds.\n")
        for row in output_rows:
            print(
                f"{row['batch_id']}: disease/biosecurity {row['disease_risk_score']:>5.1f} "
                f"({row['disease_risk_level']}); food safety {row['food_safety_risk_score']:>5.1f} "
                f"({row['food_safety_risk_level']})"
            )
            if args.scenario:
                print(
                    f"  what-if [{args.scenario}]: disease {row['scenario_disease_risk_score']:.1f} "
                    f"({row['disease_score_change']:+.1f}); food safety {row['scenario_food_safety_risk_score']:.1f} "
                    f"({row['food_safety_score_change']:+.1f})"
                )
        return 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
