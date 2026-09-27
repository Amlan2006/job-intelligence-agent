import re

ALIASES = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "golang": "Go",
    "go-lang": "Go",
    "go": "Go",
    "python": "Python",
    "rust": "Rust",
    "solidity": "Solidity",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "fastapi": "FastAPI",
    "sql": "SQL",
    "redis": "Redis",
    "ethereum": "Ethereum",
    "evm": "EVM",
    "foundry": "Foundry",
    "hardhat": "Hardhat",
    "git": "Git",
    "github actions": "GitHub Actions",
}


def normalize_skill(name: str) -> str:
    cleaned = " ".join(name.split())
    return ALIASES.get(cleaned.casefold(), cleaned)


def normalize_skills(names: list[str]) -> list[str]:
    result = {}
    for name in names:
        normalized = normalize_skill(name)
        if normalized:
            result.setdefault(normalized.casefold(), normalized)
    return sorted(result.values(), key=str.casefold)


def skill_in_quote(name: str, quote: str) -> bool:
    canonical = normalize_skill(name).casefold()
    aliases = [alias for alias, value in ALIASES.items() if value.casefold() == canonical]
    aliases.append(name.strip())
    return any(
        re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", quote, re.I)
        for alias in aliases
        if alias
    )
