# report_static.py

from typing import Dict, List

EXPLANATIONS = {
    "Flat": (
        "Flat feet occur when the medial arch is lowered or collapsed, causing more of the sole "
        "to contact the ground. This can alter lower-limb alignment and may increase stress "
        "through the knees and lower back, especially during prolonged standing."
    ),
    "Normal": (
        "A normal arch distributes weight efficiently through the foot and ankle. It typically "
        "offers a balanced foundation for walking and running, with even load sharing across the foot."
    ),
    "High": (
        "High arches (pes cavus) reduce the surface area in contact with the ground—often concentrating "
        "pressure in the heel and forefoot. This can raise the risk of discomfort, calluses, and overuse "
        "injuries without adequate cushioning."
    ),
}

CARE_TIPS = {
    "Flat": [
        "Strengthen intrinsic foot muscles (e.g., short-foot exercise) 3–4x/week.",
        "Consider supportive footwear with firm heel counters.",
        "Gradually build activity; avoid sudden jumps in training volume.",
        "If pain persists, consult a clinician for custom orthotics.",
    ],
    "Normal": [
        "Maintain general foot/ankle strength and mobility.",
        "Rotate footwear to reduce repetitive stress.",
        "Replace worn-out shoes regularly (300–500 miles of use).",
    ],
    "High": [
        "Favor cushioned shoes with softer midsoles to attenuate impact.",
        "Use metatarsal pads/insoles to spread forefoot load.",
        "Stretch calves and plantar fascia to maintain flexibility.",
    ],
    "Unknown": [
        "Retake a clear, straight-on footprint image on a flat, well-lit surface.",
        "Ensure the foot is not rotated or tilted; stand naturally and evenly.",
    ],
}

SHOE_TIPS = {
    "Flat": [
        "Stability or motion-control shoes help reduce overpronation.",
        "Look for firmer medial support and a rigid heel counter.",
    ],
    "Normal": [
        "Neutral shoes typically suffice; focus on comfort and fit.",
        "Test multiple brands/models to find your natural preference.",
    ],
    "High": [
        "Cushioned or ‘max-cushion’ shoes disperse impact better.",
        "A slightly softer midsole and a wider toe box can improve comfort.",
    ],
    "Unknown": [
        "Choose a comfortable, well-fitting neutral shoe until a definitive arch type is known.",
    ],
}

