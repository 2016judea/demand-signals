"""Shared vocabularies: sector title filters, state->region, and the need lexicon."""
import re

TITLE = {
    "Energy & utilities": r"line ?(man|men|worker|technician|apprentice)|lineworker|solar|power plant|plant operator|utility|utilities|substation|wind|energy|electric(al)? (distribution|transmission)|meter|gas|nuclear|operator",
    "Agriculture & food processing": r"farm|agri|harvest|crop|dairy|ranch|greenhouse|nursery|meat|poultry|processing|production|plant|packag|butcher|sanitation|food (production|processing|manufactur)|line worker|machine operator|operator|packer|slaughter|egg",
    "Childcare": r"child|daycare|day care|preschool|toddler|infant|teacher|nanny|early (childhood|learning)|caregiver|assistant",
    "Education": r"teach|para|special ed|educat|instruct|tutor|school|aide|behavior|classroom|professor|substitute|principal|counselor|interventionist",
    "Government & public safety": r"police|officer|security|guard|correction|detention|deputy|sheriff|patrol|dispatcher|jailer|public safety|firefight|trooper",
}

REGION = {}
for r, sts in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for s in sts.split():
        REGION[s] = r

N = {  # label -> (group, regex). Case-insensitive unless the pattern starts with (?-i)
    # credentials
    "Active RN license": ("Credential", r"rn licen[cs]e|registered nurse( \(rn\))? licen|licensed (as an? )?(registered nurse|rn)\b|licen[cs]e (as|to practice as) an? (registered nurse|rn)|compact (nursing )?licen|multi-?state licen"),
    "BLS / CPR / ACLS": ("Credential", r"\b(bls|acls|pals|cpr)\b"),
    "CNA / HHA certification": ("Credential", r"\b(cna|certified nursing assistant|hha|home health aide) (certif|licen|required)"),
    "LPN/LVN": ("Credential", r"\b(lpn|lvn)\b"),
    "CDL Class A": ("Credential", r"\b(class a cdl|cdl[- ]a\b|cdl class a)"),
    "CDL (any)": ("Credential", r"\bcdl\b"),
    "Clean driving record / MVR": ("Credential", r"(clean|good|acceptable|safe) driving record|\bmvr\b|motor vehicle record"),
    "Valid driver's license": ("Credential", r"valid driver'?s licen"),
    "Forklift certification": ("Credential", r"forklift (certif|licen|experience)|certified forklift"),
    "OSHA 10/30": ("Credential", r"\bosha[- ]?(10|30)\b"),
    "Journeyman / master licence": ("Credential", r"\bjourney(man|person)|master (electrician|plumber)|licensed (electrician|plumber)"),
    "EPA 608": ("Credential", r"\bepa (608|section 608|universal)"),
    "ASE certification": ("Credential", r"\base[- ]certif|\base certified"),
    "CPA": ("Credential", r"(?-i)\bCPA\b"),
    "Securities licences (SIE/6/7/63)": ("Credential", r"series (6|7|63|65|66)\b|\bSIE\b"),
    "Insurance producer licence": ("Credential", r"(property (and|&) casualty|p&c|life (and|&) health|producer'?s?) licen"),
    "Teaching certificate": ("Credential", r"teaching (certificat|licen|credential)|state certification in|certified teacher"),
    "Security clearance": ("Credential", r"security clearance|\bts/sci\b|top secret|secret clearance|clearance required"),
    "PE licence": ("Credential", r"(?-i)\bPE\b licen|professional engineer|\bP\.E\."),
    "PMP": ("Credential", r"(?-i)\bPMP\b"),
    "Food handler / ServSafe": ("Credential", r"servsafe|food handler"),
    "Guard card / armed licence": ("Credential", r"guard card|security (officer )?licen|armed (guard|security)"),
    "Pharmacy licence / PTCB": ("Credential", r"\bptcb\b|pharmacy technician (licen|certif|registration)|pharmacist licen|\bpharm\.?d\b"),
    "Social work licence (LCSW/LMSW)": ("Credential", r"\b(lcsw|lmsw|lpc|lmft|lpcc|lisw)\b"),
    "Bar admission": ("Credential", r"admitted to (practice|the bar)|bar admission|member (in good standing )?of the .{0,20}bar"),
    "Real estate licence": ("Credential", r"real estate licen"),
    "Cyber certs (Security+/CISSP)": ("Credential", r"security\+|cissp|cism|\bcisa\b|comptia"),
    "Cloud certs (AWS/Azure)": ("Credential", r"aws certified|azure (certif|administrator|fundamentals)|solutions architect.{0,10}certif"),
    # tools
    "Microsoft Office / Excel": ("Tool", r"\b(excel|microsoft office|ms office|office 365|microsoft 365)\b"),
    "Salesforce / CRM": ("Tool", r"\b(salesforce|hubspot|crm)\b"),
    "SAP / Oracle / NetSuite ERP": ("Tool", r"\b(sap|oracle|netsuite|dynamics 365|erp)\b"),
    "QuickBooks": ("Tool", r"quickbooks"),
    "Epic / Cerner EHR": ("Tool", r"\b(epic|cerner|meditech|ehr|emr|electronic (health|medical) record)"),
    "SQL": ("Tool", r"\bsql\b"),
    "Python": ("Tool", r"\bpython\b"),
    "Cloud (AWS/Azure/GCP)": ("Tool", r"\b(aws|azure|gcp|google cloud)\b"),
    "Kubernetes / Docker": ("Tool", r"kubernetes|docker|\bk8s\b|terraform"),
    "Tableau / Power BI": ("Tool", r"tableau|power ?bi|looker"),
    "AI / LLM / GenAI": ("Tool", r"\b(generative ai|gen ?ai|llms?|large language model|chatgpt|copilot|ai tools|ai-powered|machine learning|artificial intelligence)\b"),
    "AutoCAD / Revit / SolidWorks": ("Tool", r"autocad|revit|solidworks|civil 3d|\bcad\b"),
    "PLC / controls": ("Tool", r"\bplcs?\b|allen[- ]bradley|programmable logic"),
    "POS systems": ("Tool", r"\bpos\b|point of sale|toast|square"),
    "WMS / scanners / RF": ("Tool", r"\bwms\b|warehouse management system|rf scanner|rf gun|handheld scanner"),
    "Procore / construction software": ("Tool", r"procore|bluebeam|primavera|\bp6\b"),
    "Yardi / RealPage / AppFolio": ("Tool", r"yardi|realpage|appfolio|entrata|onesite"),
    "Workday / ADP / HRIS": ("Tool", r"\bhris\b|workday|\badp\b|ukg|paylocity|paycom"),
    "Hand & power tools": ("Tool", r"(hand|power) tools"),
    # conditions
    "Nights / overnight": ("Schedule", r"\b(night shift|nights|overnight|3rd shift|third shift|graveyard)\b"),
    "Weekends": ("Schedule", r"\bweekends?\b"),
    "Overtime": ("Schedule", r"\bovertime\b"),
    "12-hour shifts": ("Schedule", r"12[- ]?(hour|hr)s? shifts?|three 12|3x12"),
    "On-call": ("Schedule", r"\bon[- ]call\b"),
    "PRN / per diem": ("Schedule", r"\bprn\b|per diem"),
    "Travel required": ("Schedule", r"travel (required|up to|\d+%)|overnight travel|regional travel"),
    "Lift 50+ lbs": ("Physical", r"(lift|carry|move)[^.]{0,40}\b(50|55|60|70|75|80|100)\s*(lbs|pounds|lb)"),
    "Standing / on feet": ("Physical", r"stand(ing)? for (long|extended|prolonged)|on (your|their) feet|stand for \d+"),
    "Outdoors / weather": ("Physical", r"outdoor|all weather|inclement weather|extreme (heat|cold|temperatures)"),
    "Drug screen": ("Screening", r"drug (screen|test)|substance (test|screen)"),
    "Background check": ("Screening", r"background (check|screen|investigation)"),
    # offers
    "Sign-on bonus": ("Offer", r"sign[- ]?on bonus|signing bonus|hiring bonus|sign on bonus"),
    "Weekly / daily pay": ("Offer", r"weekly pay|paid weekly|daily pay|same[- ]day pay|instant pay|dailypay"),
    "Tuition / training paid": ("Offer", r"tuition (reimburse|assist)|paid training|we will train|will train|on[- ]the[- ]job training|apprenticeship"),
    "401(k) match": ("Offer", r"401\(?k\)? (match|with)|matching 401|employer match"),
    "Health benefits day one": ("Offer", r"(day one|day 1|first day) (benefits|health|medical|coverage)|benefits (start|begin|effective) (on )?(day one|day 1|the first)"),
    "Shift differential": ("Offer", r"shift diff|night diff|differential"),
    "Relocation": ("Offer", r"relocation (assistance|package|bonus|support)"),
    "Commission / bonus pay": ("Offer", r"(?<!joint )\bcommission(s|ed)?\b(?! on)|uncapped|\bote\b|on[- ]target earnings"),
    "Pension": ("Offer", r"\bpension\b|defined benefit"),
    "Employee discount": ("Offer", r"employee discount|associate discount"),
    "Equity / stock": ("Offer", r"\bequity\b|stock options|\brsus?\b|espp"),
    "Tips": ("Offer", r"\btips\b|gratuit"),
    # people / profile
    "Bilingual (Spanish)": ("Profile", r"bilingual|spanish"),
    "No experience / entry level": ("Profile", r"no experience (necessary|required|needed)|entry[- ]level|new grads? (welcome|encouraged)"),
    "High school / GED": ("Profile", r"high school diploma|\bged\b"),
    "Bachelor's degree": ("Profile", r"bachelor'?s|\bb\.?s\.?\b degree|\bba/bs\b|4[- ]year degree"),
    "Master's / advanced degree": ("Profile", r"master'?s degree|\bmba\b|\bphd\b|doctorate|advanced degree"),
    "5+ years experience": ("Profile", r"\b([5-9]|1[0-5])\+? (or more )?years"),
    "Leadership / supervise others": ("Profile", r"supervis(e|ing) (a team|staff|employees)|lead a team|direct reports|people management"),
    "Customer-facing": ("Profile", r"customer[- ]facing|client[- ]facing|excellent customer service"),
    "Remote": ("Mode", r"\bfully remote|100% remote|remote position|work from home|\bwfh\b"),
    "Hybrid": ("Mode", r"\bhybrid\b"),
}
COMPILED = {}
for k, (g, p) in N.items():
    flags = 0 if p.startswith("(?-i)") else re.I
    COMPILED[k] = re.compile(p.replace("(?-i)", ""), flags)

