using ForexAI.Application.Interfaces;
using ForexAI.Application.Services;
using ForexAI.Infrastructure.Authentication;
using ForexAI.Infrastructure.ExternalServices;
using ForexAI.Infrastructure.Identity;
using ForexAI.Infrastructure.Persistence;
using ForexAI.Infrastructure.Repositories;

using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Identity;

using Microsoft.EntityFrameworkCore;

using Microsoft.IdentityModel.Tokens;

using System.Text;
using System.Text.Json.Serialization;

using AuthenticationService =
    ForexAI.Infrastructure.Authentication.AuthenticationService;


var builder = WebApplication.CreateBuilder(args);

// ============================================================
// Configuration
// ============================================================

var configuration = builder.Configuration;


// ============================================================
// Controllers + JSON
// ============================================================

builder.Services
    .AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.Converters.Add(
            new JsonStringEnumConverter()
        );
    });


// ============================================================
// OpenAPI
// ============================================================

builder.Services.AddOpenApi();


// ============================================================
// PostgreSQL / Entity Framework
// ============================================================

var connectionString =
    configuration.GetConnectionString(
        "ForexAiDatabase"
    )
    ?? throw new InvalidOperationException(
        "Connection string 'ForexAiDatabase' was not found."
    );

builder.Services.AddDbContext<ForexAiDbContext>(
    options =>
    {
        options.UseNpgsql(connectionString);
    }
);


// ============================================================
// HTTP Context
// ============================================================

builder.Services.AddHttpContextAccessor();


// ============================================================
// ASP.NET Core Identity
// ============================================================

builder.Services
    .AddIdentityCore<ApplicationUser>()
    .AddRoles<IdentityRole<Guid>>()
    .AddEntityFrameworkStores<ForexAiDbContext>()
    .AddSignInManager();


// ============================================================
// JWT Configuration
// ============================================================

var jwtSection =
    configuration.GetSection("Jwt");

var jwtIssuer =
    jwtSection["Issuer"]
    ?? throw new InvalidOperationException(
        "JWT configuration is missing 'Jwt:Issuer'."
    );

var jwtAudience =
    jwtSection["Audience"]
    ?? throw new InvalidOperationException(
        "JWT configuration is missing 'Jwt:Audience'."
    );

var jwtKey =
    jwtSection["Key"];

if (string.IsNullOrWhiteSpace(jwtKey))
{
    throw new InvalidOperationException(
        "JWT configuration is missing 'Jwt:Key'. " +
        "Check appsettings.json and appsettings.Development.json."
    );
}

if (Encoding.UTF8.GetByteCount(jwtKey) < 32)
{
    throw new InvalidOperationException(
        "JWT key must be at least 32 bytes long."
    );
}

var signingKey =
    new SymmetricSecurityKey(
        Encoding.UTF8.GetBytes(jwtKey)
    );


// ============================================================
// Authentication
// ============================================================
//
// DEVELOPMENT
// ----------------
// Uses DevelopmentAuthenticationHandler.
//
// PRODUCTION
// ----------------
// Uses JWT bearer authentication.
//
// There must only be ONE AddAuthentication()
// registration.
//

if (builder.Environment.IsDevelopment())
{
    builder.Services
        .AddAuthentication(options =>
        {
            options.DefaultAuthenticateScheme =
                "Development";

            options.DefaultChallengeScheme =
                "Development";
        })
        .AddScheme<
            AuthenticationSchemeOptions,
            DevelopmentAuthenticationHandler>(
                "Development",
                _ =>
                {
                }
        );
}
else
{
    builder.Services
        .AddAuthentication(options =>
        {
            options.DefaultAuthenticateScheme =
                JwtBearerDefaults.AuthenticationScheme;

            options.DefaultChallengeScheme =
                JwtBearerDefaults.AuthenticationScheme;
        })
        .AddJwtBearer(options =>
        {
            options.TokenValidationParameters =
                new TokenValidationParameters
                {
                    ValidateIssuer = true,
                    ValidateAudience = true,
                    ValidateLifetime = true,
                    ValidateIssuerSigningKey = true,

                    ValidIssuer = jwtIssuer,
                    ValidAudience = jwtAudience,

                    IssuerSigningKey = signingKey,

                    ClockSkew =
                        TimeSpan.FromMinutes(1)
                };
        });
}

builder.Services.AddAuthorization();


// ============================================================
// Current User
// ============================================================
//
// DEVELOPMENT
// ----------------
// Always resolves to the configured development user.
//
// PRODUCTION
// ----------------
// Reads the authenticated user from HttpContext.
//

if (builder.Environment.IsDevelopment())
{
    var developmentUserId =
        builder.Configuration.GetValue<Guid>(
            "DevelopmentUser:UserId");

    if (developmentUserId == Guid.Empty)
    {
        throw new InvalidOperationException(
            "DevelopmentUser:UserId is missing or invalid."
        );
    }

    builder.Services.AddScoped<ICurrentUserService>(
        _ => new DevelopmentCurrentUserService(
            developmentUserId));
}
else
{
    builder.Services.AddScoped<
        ICurrentUserService,
        CurrentUserService>();
}


// ============================================================
// Application Authentication Services
// ============================================================

builder.Services.AddScoped<
    ForexAI.Application.Interfaces.IAuthenticationService,
    AuthenticationService>();

builder.Services.AddScoped<
    JwtTokenService>();


// ============================================================
// Repositories
// ============================================================

builder.Services.AddScoped<
    ITradingSignalRepository,
    TradingSignalRepository>();

builder.Services.AddScoped<
    ISignalAuditRepository,
    SignalAuditRepository>();


// ============================================================
// Application Services
// ============================================================
builder.Services.AddScoped<
    MarketDataService>();


builder.Services.AddScoped<
    AnalyzeMarketService>();

builder.Services.AddScoped<
    SignalGenerationService>();

builder.Services.AddScoped<
    SignalHistoryService>();

builder.Services.AddScoped<
    SignalAuditService>();
builder.Services.AddScoped<
    ForexAI.Application.Interfaces.IForexPairRepository,
    ForexAI.Infrastructure.Repositories.ForexPairRepository>();

builder.Services.AddScoped<
    ForexPairService>();

// ============================================================
// AI Analysis Client
// ============================================================
//
// Python API:
//
// http://127.0.0.1:8000
//
// Configuration:
//
// "PythonApi": {
//     "BaseUrl": "http://127.0.0.1:8000",
//     "ApiKey": ""
// }
//
//

var pythonBaseUrl =
    configuration["PythonApi:BaseUrl"]
    ?? "http://127.0.0.1:8000";

// The Python service is public on a hosted deployment, so its X-API-Key
// guard must be satisfied here or every gateway call would be rejected.
// Unset keeps the local guard-free development behaviour.
var pythonApiKey =
    configuration["PythonApi:ApiKey"];

builder.Services.AddHttpClient<
    IAiAnalysisClient,
    PythonAiAnalysisClient>(
    client =>
    {
        client.BaseAddress = new Uri(pythonBaseUrl);
        client.Timeout = TimeSpan.FromMinutes(3); // 180 second

        if (!string.IsNullOrWhiteSpace(pythonApiKey))
        {
            client.DefaultRequestHeaders.Add(
                "X-API-Key",
                pythonApiKey);
        }
    });


builder.Services.AddHttpClient<
    ForexAI.Application.Interfaces.IMarketDataClient,
    ForexAI.Infrastructure.ExternalServices.PythonMarketDataClient>(
    client =>
    {
        client.BaseAddress = new Uri(pythonBaseUrl);
        client.Timeout = TimeSpan.FromSeconds(30);

        if (!string.IsNullOrWhiteSpace(pythonApiKey))
        {
            client.DefaultRequestHeaders.Add(
                "X-API-Key",
                pythonApiKey);
        }
    });


// ============================================================
// CORS
// ============================================================

var allowedOrigins =
    configuration
        .GetSection("Cors:AllowedOrigins")
        .Get<string[]>()
    ?? Array.Empty<string>();

builder.Services.AddCors(
    options =>
    {
        options.AddPolicy(
            "ForexAiDashboard",
            policy =>
            {
                policy
                    .WithOrigins(allowedOrigins)
                    .AllowAnyHeader()
                    .AllowAnyMethod();
            });
    });
// ============================================================
// Build
// ============================================================

var app = builder.Build();


// ============================================================
// HTTP Pipeline
// ============================================================

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

if (configuration.GetValue<bool>("HttpsRedirection:Enabled"))
{
    app.UseHttpsRedirection();
}

app.UseCors(
    "ForexAiDashboard");

// IMPORTANT:
// Authentication MUST run before Authorization.

app.UseAuthentication();

app.UseAuthorization();

// Liveness probe for orchestrators and uptime monitors (Render health
// checks, UptimeRobot). Anonymous by design: it has to answer before
// authentication and it exposes nothing but a status string. Registered
// before MapControllers so it wins over the SPA fallback.
app.MapGet(
    "/health",
    () => Results.Ok(
        new
        {
            Status = "ForexAI API is running"
        }))
    .AllowAnonymous();

app.MapControllers();


if (args.Contains("--migrate", StringComparer.OrdinalIgnoreCase))
{
    using var scope = app.Services.CreateScope();

    var db = scope.ServiceProvider.GetRequiredService<ForexAiDbContext>();

    await db.Database.MigrateAsync();

    return;
}

app.Run();// in Program.cs, under // Repositories

