FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build

WORKDIR /src

# Copy project files first for Docker layer caching
COPY ForexAI.Domain/ForexAI.Domain.csproj ForexAI.Domain/
COPY ForexAI.Application/ForexAI.Application.csproj ForexAI.Application/
COPY ForexAI.Infrastructure/ForexAI.Infrastructure.csproj ForexAI.Infrastructure/
COPY ForexAI.Api/ForexAI.Api.csproj ForexAI.Api/

# Restore only the API and its referenced projects.
# Tests are not needed in the runtime image.
RUN dotnet restore ForexAI.Api/ForexAI.Api.csproj

# Copy source code
COPY . .

# Build and publish the API
RUN dotnet publish ForexAI.Api/ForexAI.Api.csproj \
    -c Release \
    -o /app/publish \
    /p:UseAppHost=false


FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS runtime

WORKDIR /app

# curl is needed by the container healthcheck below (GET /health); the
# aspnet base image ships neither curl nor wget. This is the only package
# added to the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build --chown=app:app /app/publish .

# DataProtection keys must live on the persistent volume and be writable by
# the non-root runtime user (the aspnet image ships an "app" user, uid 1654).
# Compose mounts forexai-dataprotection-keys at /home/app/.aspnet/DataProtection-Keys.
ENV ASPNETCORE_URLS=http://+:8080 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 8080

# Liveness: /health never touches the database or the Python service, so a
# healthy container means the process is up, not that dependencies are good.
# Use GET /health/ready (loopback) for the full dependency picture.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

USER app

ENTRYPOINT ["dotnet", "ForexAI.Api.dll"]