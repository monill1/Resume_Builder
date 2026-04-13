export const sampleResume = {
  basics: {
    full_name: "Monil Panchal",
    headline: "AI/ML Engineer | Backend Developer | Data Analyst",
    email: "panchalmonil22@gmail.com",
    phone: "+91 70165 65034",
    location: "Ahmedabad, Gujarat, India",
    linkedin: "https://www.linkedin.com/in/monil-panchal/",
    github: "https://github.com/monill1",
    website: "",
    summary:
      "Results-driven AI/ML, backend, and data analytics engineer with hands-on experience building scalable APIs, analytics workflows, and machine-learning solutions. Strong in Python, FastAPI, Django, SQL, data visualization, and ATS-friendly resume writing.",
  },
  skills: [
    { name: "Languages & Querying", items: ["Python", "SQL", "JavaScript", "TypeScript"] },
    { name: "Backend", items: ["FastAPI", "Django", "REST APIs", "API Integrations"] },
    { name: "Frontend", items: ["React.js", "HTML", "CSS"] },
    { name: "Data & ML", items: ["Pandas", "NumPy", "Scikit-learn", "Matplotlib", "Seaborn"] },
    { name: "Tools & Cloud", items: ["Git", "GitHub", "Jupyter Notebook", "AWS"] },
  ],
  experience: [
    {
      company: "Freelancing",
      company_link: "",
      role: "Data Analyst",
      location: "Remote, India",
      start_date: "2025",
      end_date: "",
      current: true,
      achievements: [
        "Delivered custom analytics and reporting solutions for small and mid-sized businesses.",
        "Collected, cleaned, and transformed raw data from Excel, CSV, and SQL databases.",
        "Helped stakeholders identify trends, improve reporting quality, and support data-driven decisions.",
      ],
    },
    {
      company: "BrainerHub",
      company_link: "https://www.brainerhub.com/",
      role: "Python Developer (AI/ML) Intern",
      location: "Ahmedabad",
      start_date: "2024",
      end_date: "2025",
      current: false,
      achievements: [
        "Built and optimized backend features in Python for client-facing solutions.",
        "Created REST APIs using FastAPI and Flask for business logic and data processing.",
        "Prepared visual reports and collaborated with product and frontend teams to ship end-to-end features.",
      ],
    },
  ],
  projects: [
    {
      name: "Movie Recommender System",
      tech_stack: "Python, FastAPI, React, Pandas, NumPy, Scikit-learn",
      link: "https://github.com/monill1/movie-recommender-system",
      highlights: [
        "Developed a full-stack recommendation system with frontend, backend, and ML layers.",
        "Implemented content-based recommendation logic using cosine similarity and metadata features.",
        "Built a clean React UI and FastAPI APIs for real-time recommendations.",
      ],
    },
  ],
  education: [
    {
      institution: "International Institute of Information Technology Bangalore (IIITB)",
      degree: "Post Graduate Diploma in Data Science",
      duration: "2022 - 2023",
      score: "CGPA: 3.57 / 4.0",
      location: "Hybrid",
    },
  ],
  certifications: [
    { title: "Python and SQL Certification", issuer: "DataCamp / HackerRank / CodeChef", year: "2022" },
    { title: "The Fundamentals of Digital Marketing", issuer: "Google", year: "2024" },
  ],
  section_order: ["summary", "skills", "experience", "projects", "education", "certifications"],
};
