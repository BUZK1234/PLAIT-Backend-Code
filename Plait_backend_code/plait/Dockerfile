FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /Plait_backend/

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        r-base \
        r-base-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install R packages
RUN Rscript -e "install.packages(c('stats', 'DataVisualizations', 'caret', 'plotly', 'jsonlite', 'webshot', 'httr'), repos='https://cran.rstudio.com/')"

# Copy project files
COPY . .

# Copy R script into container
#COPY Server/*DBS_Call.R Server/*DBS_Predict.R  Server/*mRNA_DBS_knn_M.rds.tex Server/*mRNA_TestX.lrn Server/*mRNA_TestY.cls /Plait_backend/

# Set executable permissions for R script
#RUN chmod +x Dummy_file.R

# Install Python dependencies
COPY requirements.txt /Plait_backend/
RUN pip install -r requirements.txt

# Command to run migrations and start Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8020", "--noreload"]
