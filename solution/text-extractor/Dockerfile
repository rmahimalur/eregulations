FROM public.ecr.aws/lambda/python:3.11

ENV HOSTNAME="text-extractor"
ENV EXTERNAL_PORT="6000"
#ENV PROXY_PARAMS="--enable-async"
ENV PROXY_PARAMS=""
ENV STARTUP_CMD="app.text_extractor.handler"
# Copy lambda-proxy
COPY lambda-proxy /proxy

# Install packages required by lambda-proxy
RUN pip install -r /proxy/requirements.txt

# Copy function code
# Will be overridden locally
COPY text-extractor ${LAMBDA_TASK_ROOT}/app

# Install binary dependencies
RUN xargs yum install -y < app/packages.txt

# Install the required packages
RUN pip install -r app/requirements.txt

# Set the custom entrypoint to run lambda-proxy on startup
ENTRYPOINT /proxy/startup.sh
