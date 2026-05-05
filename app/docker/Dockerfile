FROM python:3.11

# Set working directory
WORKDIR /app

# Copy requirements file
COPY docker/requirements.txt .

# Install PyTorch with CUDA 12.4 and other requirements
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 && \
    pip install -r requirements.txt

# Expose port for API
EXPOSE 5000

CMD ["python", "/app/spikenet2.py"]