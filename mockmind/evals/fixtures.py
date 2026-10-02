"""Fixed resume/JD pairs used to generate interview plans for eval runs."""

SAMPLE_RESUME = """
Priya Sharma
Software Engineer

EXPERIENCE
Backend Engineer, TechNova Solutions (2022-2026)
- Built and maintained a FastAPI microservice handling resume parsing and
  structured data extraction, processing ~50k documents/month.
- Migrated a monolithic Flask app to a containerized microservice architecture
  on Kubernetes, reducing deployment time from 45 minutes to 6 minutes.
- Integrated Gemini-based LLM pipelines for document classification, improving
  classification accuracy from 78% to 94%.

Software Engineering Intern, DataWorks Inc. (2021)
- Built internal dashboards using React and PostgreSQL for the data team.

SKILLS
Python, FastAPI, Docker, Kubernetes, PostgreSQL, Redis, Google Gemini API,
React, TypeScript, CI/CD (GitHub Actions)

EDUCATION
B.Tech Computer Science, National Institute of Technology (2017-2021)
"""

SAMPLE_JOB_DESCRIPTION = """
AI Engineer — Applied Machine Learning
TechNova Solutions | Bangalore, India (Hybrid) | Full-time

About the Role
We're looking for an AI Engineer to join our Applied ML team, building and
shipping production-grade machine learning and LLM-powered systems.

Responsibilities
- Design, train, and fine-tune ML/LLM models for classification, retrieval-
  augmented generation (RAG), and structured extraction.
- Build and maintain production ML pipelines: ingestion, training,
  evaluation, and deployment.
- Deploy models as scalable APIs/microservices using FastAPI, Docker, and
  Kubernetes.
- Implement monitoring and evaluation frameworks to track model drift,
  latency, and output quality in production.

Required Qualifications
- 3+ years of experience building and deploying machine learning systems in
  production.
- Strong proficiency in Python and ML frameworks.
- Hands-on experience with LLMs, prompt engineering, embeddings.
- Experience with cloud platforms and containerization (Docker, Kubernetes).
- Strong SQL and data manipulation skills.

Nice to Have
- Experience with multi-agent systems or agentic frameworks.
- Experience with real-time/streaming ML inference.
"""
