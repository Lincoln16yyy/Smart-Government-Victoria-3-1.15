"""Research weights and benefit text for opportunities checked against Victoria 3."""

CONTEXTS = {
    # Descriptions name the precise signal used by the country trigger.
    "infrastructure": (
        "Há um estado incorporado com infraestrutura sobrecarregada.",
        "An incorporated state is using more infrastructure than it has.",
    ),
}

# Technology, context, priority score, benefit in Brazilian Portuguese and English.
POLICY = (
    ("railways", "infrastructure", 90,
     "Desbloqueia ferrovias, que fornecem infraestrutura quando operacionais.",
     "Unlocks railways, which provide infrastructure when operational."),
)
