# # Use official lightweight Python image
# FROM python:3.10-slim

# # Set the working directory in the container
# WORKDIR /app

# # Copy the requirements file into the container
# COPY requirements.txt .

# # Install dependencies (ignoring warnings that might halt build)
# RUN pip install --no-cache-dir -r requirements.txt

# # Download Spacy and NLTK language models before the app starts to speed up container booting
# RUN python -m spacy download en_core_web_sm
# RUN python -c "import nltk; nltk.download('punkt', quiet=True)"

# # Copy the current directory contents into the container at /app
# COPY . .

# # Expose port 5000 so the outside world can talk to the Flask server
# EXPOSE 5000

# # Tell Docker how to run the application (in production mode using Gunicorn/Flask)
# CMD ["python", "app.py"]



# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first (better Docker caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLP models
RUN python -m spacy download en_core_web_sm
RUN python - <<EOF
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
EOF

# Copy project files
COPY . .

# Expose Flask port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]