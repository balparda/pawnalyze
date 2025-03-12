# Use a lightweight Python base image
FROM python:3.9-slim

# Create a working directory in the container
WORKDIR /app

# (Optional) set environment variables so we can install more easily
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy requirements file first, so pip install can be cached
COPY requirements.txt .

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     p7zip-full \
#     && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of project code
COPY . .

# We assume your code references `_PGN_DATA_DIR` somewhere in a config, e.g.:
#   _PGN_DATA_DIR = base.MODULE_PRIVATE_DIR(__file__, '.pawnalyze-data')
# So we want a volume for it. We'll mount the host's 100GB DB here at runtime:
VOLUME ["/app/.pawnalyze-data"]

# Entrypoint or default command:
# If you usually run "pawningest.py" or "pawnmaintain.py",
# you can define a default command here:
CMD ["python", "pawningest.py", "--help"]
