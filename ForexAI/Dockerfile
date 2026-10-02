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

COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:8080

EXPOSE 8080

ENTRYPOINT ["dotnet", "ForexAI.Api.dll"]