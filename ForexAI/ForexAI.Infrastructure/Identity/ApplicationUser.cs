using Microsoft.AspNetCore.Identity;

namespace ForexAI.Infrastructure.Identity;

public sealed class ApplicationUser : IdentityUser<Guid>
{
    public Guid DomainUserId { get; set; }
}