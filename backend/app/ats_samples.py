from __future__ import annotations

from .models import ResumePayload


ATS_SAMPLE_CASES = {
    "backend_developer": {
        "job_title": "Backend Developer",
        "job_description": """
Backend Developer
Required qualifications:
- 3+ years of experience building Python backend services.
- Strong experience with FastAPI or Django, REST APIs, PostgreSQL, Docker, and AWS.
- Experience designing scalable microservices and CI/CD pipelines.
- Bachelor's degree in Computer Science or related field.
Preferred qualifications:
- Experience with Kafka, Redis, and Kubernetes.
- Strong communication and stakeholder collaboration.
Responsibilities:
- Build APIs, own backend architecture, and partner with frontend and product teams.
""".strip(),
        "resume": ResumePayload.model_validate(
            {
                "basics": {
                    "full_name": "Aarav Mehta",
                    "headline": "Backend Engineer | Python API Developer",
                    "email": "aarav@example.com",
                    "phone": "+91 98765 43210",
                    "location": "Bengaluru, India",
                    "linkedin": "https://www.linkedin.com/in/aarav-mehta/",
                    "github": "https://github.com/aaravmehta",
                    "summary": (
                        "Backend engineer with 4 years of experience building Python APIs, scaling services, and shipping "
                        "cloud-native applications with FastAPI, PostgreSQL, Docker, and AWS."
                    ),
                },
                "skills": [
                    {"name": "Backend", "items": ["Python", "FastAPI", "REST APIs", "PostgreSQL", "Docker", "AWS"]},
                    {"name": "Platform", "items": ["Git", "CI/CD", "Redis"]},
                ],
                "experience": [
                    {
                        "company": "Nimbus Labs",
                        "company_link": None,
                        "role": "Backend Engineer",
                        "location": "Bengaluru",
                        "start_date": "2022",
                        "end_date": None,
                        "current": True,
                        "achievements": [
                            "Built FastAPI services handling 1.2M monthly requests and reduced latency by 34%.",
                            "Designed PostgreSQL schemas and Docker-based deployments on AWS ECS.",
                            "Partnered with product managers and frontend engineers to deliver customer-facing APIs.",
                        ],
                    },
                    {
                        "company": "Orbit Stack",
                        "company_link": None,
                        "role": "Python Developer",
                        "location": "Remote",
                        "start_date": "2020",
                        "end_date": "2022",
                        "current": False,
                        "achievements": [
                            "Maintained Django and REST API integrations for SaaS workflows.",
                            "Implemented CI/CD automation and Redis caching for internal services.",
                        ],
                    },
                ],
                "projects": [
                    {
                        "name": "Event Stream Platform",
                        "tech_stack": "Python, FastAPI, Kafka, Docker, AWS",
                        "link": "https://github.com/aaravmehta/event-stream-platform",
                        "highlights": [
                            "Built a service prototype that consumed Kafka events and exposed FastAPI endpoints.",
                            "Documented deployment steps and monitoring guardrails for production readiness.",
                        ],
                    }
                ],
                "education": [
                    {
                        "institution": "Visvesvaraya Technological University",
                        "degree": "Bachelor of Engineering in Computer Science",
                        "duration": "2016 - 2020",
                        "score": "8.6 CGPA",
                        "location": "Bengaluru",
                    }
                ],
                "certifications": [{"title": "AWS Certified Cloud Practitioner", "issuer": "AWS", "year": "2023"}],
            }
        ),
    },
    "data_analyst": {
        "job_title": "Data Analyst",
        "job_description": """
Data Analyst
Requirements:
- 2+ years of experience with SQL, Excel, Tableau or Power BI, and dashboarding.
- Strong analytical thinking, statistics, and stakeholder communication.
- Experience cleaning large datasets and building actionable reporting.
Preferred:
- Exposure to Python, experimentation, and product analytics.
Responsibilities:
- Build dashboards, monitor KPIs, and communicate insights to business partners.
""".strip(),
        "resume": ResumePayload.model_validate(
            {
                "basics": {
                    "full_name": "Riya Shah",
                    "headline": "Data Analyst | BI Reporting Specialist",
                    "email": "riya@example.com",
                    "phone": "+91 91234 56789",
                    "location": "Pune, India",
                    "linkedin": "https://www.linkedin.com/in/riya-shah/",
                    "github": "",
                    "summary": (
                        "Data analyst with 3 years of experience using SQL, Excel, Tableau, and Power BI to translate "
                        "business data into KPI dashboards and stakeholder-ready insights."
                    ),
                },
                "skills": [
                    {"name": "Analytics", "items": ["SQL", "Excel", "Tableau", "Power BI", "Statistics"]},
                    {"name": "Workflow", "items": ["Data Analysis", "Data Visualization", "Stakeholder Management"]},
                ],
                "experience": [
                    {
                        "company": "Insight Cart",
                        "company_link": None,
                        "role": "Data Analyst",
                        "location": "Pune",
                        "start_date": "2023",
                        "end_date": None,
                        "current": True,
                        "achievements": [
                            "Built Tableau and Power BI dashboards used by finance and growth teams each week.",
                            "Cleaned 5M+ row datasets with SQL and Excel, improving reporting accuracy by 19%.",
                            "Presented KPI trends and business recommendations to cross-functional stakeholders.",
                        ],
                    }
                ],
                "projects": [],
                "education": [
                    {
                        "institution": "Savitribai Phule Pune University",
                        "degree": "Bachelor of Commerce",
                        "duration": "2018 - 2021",
                        "score": "",
                        "location": "Pune",
                    }
                ],
                "certifications": [],
            }
        ),
    },
    "aiml_engineer": {
        "job_title": "AI/ML Engineer",
        "job_description": """
AI/ML Engineer
Required qualifications:
- 3+ years building machine learning systems in Python.
- Strong experience with PyTorch or TensorFlow, NLP, feature engineering, and MLOps.
- Experience deploying model-backed APIs and working with cloud infrastructure.
Preferred:
- FastAPI, Docker, AWS, and experience with LLM or generative AI products.
Responsibilities:
- Build production models, evaluate performance, and partner with product teams on AI features.
""".strip(),
        "resume": ResumePayload.model_validate(
            {
                "basics": {
                    "full_name": "Kabir Nair",
                    "headline": "Machine Learning Engineer | NLP Developer",
                    "email": "kabir@example.com",
                    "phone": "+91 99887 77665",
                    "location": "Hyderabad, India",
                    "linkedin": "https://www.linkedin.com/in/kabir-nair/",
                    "github": "https://github.com/kabirnair",
                    "summary": (
                        "Machine learning engineer specializing in NLP, model deployment, and production-grade Python services. "
                        "Hands-on with PyTorch, FastAPI, Docker, AWS, and LLM evaluation workflows."
                    ),
                },
                "skills": [
                    {"name": "ML", "items": ["Python", "Machine Learning", "Natural Language Processing", "PyTorch", "Feature Engineering"]},
                    {"name": "Deployment", "items": ["FastAPI", "Docker", "AWS", "MLOps"]},
                ],
                "experience": [
                    {
                        "company": "Neural Forge",
                        "company_link": None,
                        "role": "ML Engineer",
                        "location": "Hyderabad",
                        "start_date": "2022",
                        "end_date": None,
                        "current": True,
                        "achievements": [
                            "Built PyTorch NLP models that improved classification accuracy by 11%.",
                            "Deployed FastAPI inference services with Docker on AWS for internal AI products.",
                            "Worked on evaluation loops for LLM-assisted support automation.",
                        ],
                    }
                ],
                "projects": [
                    {
                        "name": "Support Ticket Router",
                        "tech_stack": "Python, PyTorch, FastAPI, Docker",
                        "link": "",
                        "highlights": [
                            "Implemented feature engineering and model evaluation for an NLP routing workflow.",
                        ],
                    }
                ],
                "education": [
                    {
                        "institution": "IIIT Hyderabad",
                        "degree": "Master of Technology in AI",
                        "duration": "2020 - 2022",
                        "score": "",
                        "location": "Hyderabad",
                    }
                ],
                "certifications": [],
            }
        ),
    },
    "product_analyst": {
        "job_title": "Product Analyst",
        "job_description": """
Product Analyst
Requirements:
- 2+ years of experience in product analytics or business analytics.
- Strong SQL, experimentation, dashboarding, and stakeholder storytelling.
- Experience with Mixpanel, Amplitude, or similar product analytics tools.
- Comfortable partnering with product managers and growth teams.
Preferred:
- Python, statistics, and A/B testing design.
Responsibilities:
- Analyze funnels, define KPIs, surface growth insights, and influence roadmap decisions.
""".strip(),
        "resume": ResumePayload.model_validate(
            {
                "basics": {
                    "full_name": "Neha Kulkarni",
                    "headline": "Product Analyst | Growth Analytics",
                    "email": "neha@example.com",
                    "phone": "+91 90123 45678",
                    "location": "Mumbai, India",
                    "linkedin": "https://www.linkedin.com/in/neha-kulkarni/",
                    "github": "",
                    "summary": (
                        "Product analyst with experience in funnel analysis, KPI reporting, and stakeholder storytelling "
                        "using SQL, Mixpanel, dashboards, and experimentation frameworks."
                    ),
                },
                "skills": [
                    {"name": "Product Analytics", "items": ["SQL", "Mixpanel", "Amplitude", "Product Analytics", "A/B Testing"]},
                    {"name": "Communication", "items": ["Stakeholder Management", "Communication", "Data Visualization"]},
                ],
                "experience": [
                    {
                        "company": "Growth Lane",
                        "company_link": None,
                        "role": "Product Analyst",
                        "location": "Mumbai",
                        "start_date": "2023",
                        "end_date": None,
                        "current": True,
                        "achievements": [
                            "Analyzed user funnels in Mixpanel and identified experiments that improved activation by 8%.",
                            "Built KPI dashboards and narrated product insights to PMs and growth stakeholders.",
                            "Used SQL to define metrics and evaluate A/B test results for onboarding flows.",
                        ],
                    }
                ],
                "projects": [],
                "education": [
                    {
                        "institution": "Mumbai University",
                        "degree": "Bachelor of Management Studies",
                        "duration": "2019 - 2022",
                        "score": "",
                        "location": "Mumbai",
                    }
                ],
                "certifications": [],
            }
        ),
    },
}
