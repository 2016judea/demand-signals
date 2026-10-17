"""Pull active US job postings from Indeed (via JobSpy) across sectors x metros.

Writes one parquet per (sector, term, metro) cell into data/raw/ so a crash resumes.
"""
import os, sys, time, random, itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from jobspy import scrape_jobs

SECTORS = {
    "Healthcare": ["registered nurse", "medical assistant", "physician", "physical therapist"],
    "Senior & home care": ["caregiver", "certified nursing assistant"],
    "Software & IT": ["software engineer", "IT support", "data engineer", "cybersecurity"],
    "AI & data": ["machine learning engineer", "data analyst"],
    "Finance & accounting": ["accountant", "financial analyst", "bookkeeper"],
    "Banking & insurance": ["bank teller", "insurance agent", "claims adjuster"],
    "Sales": ["account executive", "sales representative"],
    "Marketing": ["marketing manager", "social media"],
    "Customer service": ["customer service representative", "call center"],
    "Admin & office": ["administrative assistant", "receptionist", "office manager"],
    "HR & recruiting": ["recruiter", "human resources generalist"],
    "Manufacturing": ["machine operator", "production supervisor", "quality inspector", "CNC machinist"],
    "Engineering": ["mechanical engineer", "electrical engineer", "civil engineer"],
    "Skilled trades": ["electrician", "HVAC technician", "plumber", "welder", "maintenance technician"],
    "Construction": ["construction laborer", "project manager construction", "superintendent construction"],
    "Transportation": ["CDL truck driver", "delivery driver", "dispatcher"],
    "Warehouse & logistics": ["warehouse associate", "forklift operator", "logistics coordinator", "supply chain analyst"],
    "Retail": ["retail sales associate", "store manager", "cashier"],
    "Restaurants & hospitality": ["line cook", "server restaurant", "restaurant manager", "hotel front desk"],
    "Education": ["teacher", "paraprofessional", "special education"],
    "Childcare": ["childcare teacher", "daycare"],
    "Legal": ["paralegal", "attorney"],
    "Government & public safety": ["police officer", "security officer", "correctional officer"],
    "Real estate & property": ["property manager", "leasing consultant", "real estate agent"],
    "Energy & utilities": ["lineman", "solar installer", "power plant operator"],
    "Automotive": ["automotive technician", "diesel mechanic"],
    "Cleaning & facilities": ["janitor", "housekeeper", "facilities manager"],
    "Pharma & life sciences": ["pharmacist", "pharmacy technician", "clinical research", "lab technician"],
    "Social services": ["case manager", "behavioral health technician", "social worker"],
    "Agriculture & food processing": ["farm worker", "food production", "meat processing"],
}

METROS = {
    "Northeast": ["New York, NY", "Boston, MA", "Philadelphia, PA", "Pittsburgh, PA"],
    "Midwest": ["Chicago, IL", "Minneapolis, MN", "Detroit, MI", "Columbus, OH", "Kansas City, MO"],
    "South": ["Dallas, TX", "Houston, TX", "Atlanta, GA", "Miami, FL", "Charlotte, NC", "Nashville, TN"],
    "West": ["Los Angeles, CA", "San Francisco, CA", "Seattle, WA", "Phoenix, AZ", "Denver, CO", "Salt Lake City, UT"],
}

RESULTS = int(os.environ.get("RESULTS", 50))
OUT = "data/raw"
os.makedirs(OUT, exist_ok=True)


def slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower())


def cell(sector, term, region, metro):
    path = f"{OUT}/{slug(sector)}__{slug(term)}__{slug(metro)}.parquet"
    if os.path.exists(path):
        return path, -1
    for attempt in range(4):
        try:
            df = scrape_jobs(site_name=["indeed"], search_term=term, location=metro,
                             results_wanted=RESULTS, hours_old=720, country_indeed="USA",
                             description_format="markdown", distance=50)
            df["q_sector"], df["q_term"], df["q_region"], df["q_metro"] = sector, term, region, metro
            df["pulled_at"] = pd.Timestamp.now("UTC")
            df = df.astype({c: "string" for c in df.columns if df[c].dtype == object})
            df.to_parquet(path)
            return path, len(df)
        except Exception as e:
            time.sleep(5 * (attempt + 1) + random.random() * 5)
            err = e
    print("FAIL", sector, term, metro, err, flush=True)
    return path, 0


jobs = [(s, t, r, m) for s, ts in SECTORS.items() for t in ts for r, ms in METROS.items() for m in ms]
print(len(jobs), "cells", flush=True)
done = 0
with ThreadPoolExecutor(int(os.environ.get("WORKERS", 6))) as ex:
    futs = [ex.submit(cell, *j) for j in jobs]
    for f in as_completed(futs):
        done += 1
        p, n = f.result()
        if done % 50 == 0:
            print(done, "/", len(jobs), flush=True)
print("DONE", flush=True)
