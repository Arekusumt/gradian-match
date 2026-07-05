# src/gradianmatch/resume_model.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict

@dataclass
class Profile: network: str = ""; url: str = ""
@dataclass
class Basics:
    name: str = ""; label: str = ""; email: str = ""; phone: str = ""
    url: str = ""; summary: str = ""; location: str = ""
    profiles: list[Profile] = field(default_factory=list)
@dataclass
class Work:
    name: str = ""; position: str = ""; startDate: str = ""; endDate: str = ""
    summary: str = ""; highlights: list[str] = field(default_factory=list)
@dataclass
class Education:
    institution: str = ""; area: str = ""; studyType: str = ""
    startDate: str = ""; endDate: str = ""
@dataclass
class Skill:
    name: str = ""; level: str = ""; keywords: list[str] = field(default_factory=list)
@dataclass
class Project:
    name: str = ""; description: str = ""; url: str = ""
    highlights: list[str] = field(default_factory=list)
@dataclass
class Language: language: str = ""; fluency: str = ""
@dataclass
class Certificate: name: str = ""; issuer: str = ""; date: str = ""

@dataclass
class Resume:
    basics: Basics = field(default_factory=Basics)
    work: list[Work] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)
    certificates: list[Certificate] = field(default_factory=list)

    def all_skill_terms(self) -> set[str]:
        terms: set[str] = set()
        for s in self.skills:
            if s.name: terms.add(s.name.lower())
            terms.update(k.lower() for k in s.keywords)
        return terms

def _mk(cls, d: dict):
    fields = cls.__dataclass_fields__
    return cls(**{k: v for k, v in d.items() if k in fields})

def resume_from_dict(d: dict) -> Resume:
    b = d.get("basics", {}) or {}
    basics = _mk(Basics, {k: v for k, v in b.items() if k != "profiles"})
    basics.profiles = [_mk(Profile, p) for p in b.get("profiles", []) or []]
    return Resume(
        basics=basics,
        work=[_mk(Work, w) for w in d.get("work", []) or []],
        education=[_mk(Education, e) for e in d.get("education", []) or []],
        skills=[_mk(Skill, s) for s in d.get("skills", []) or []],
        projects=[_mk(Project, p) for p in d.get("projects", []) or []],
        languages=[_mk(Language, l) for l in d.get("languages", []) or []],
        certificates=[_mk(Certificate, c) for c in d.get("certificates", []) or []],
    )

def resume_to_dict(r: Resume) -> dict:
    return asdict(r)
