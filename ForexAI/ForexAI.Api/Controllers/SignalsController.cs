using ForexAI.Application.Contracts.Signals;
using ForexAI.Application.Interfaces;
using ForexAI.Application.Services;
using ForexAI.Domain.Entities;
using ForexAI.Domain.Enums;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace ForexAI.Api.Controllers;

[Authorize]
[ApiController]
[Route("api/[controller]")]
public class SignalsController : ControllerBase
{
    private readonly ITradingSignalRepository _repository;
    private readonly ISignalAuditRepository _auditRepository;
    private readonly SignalHistoryService _signalHistoryService;
    private readonly SignalAuditService _signalAuditService;

    public SignalsController(
        ITradingSignalRepository repository,
        ISignalAuditRepository auditRepository,
        SignalHistoryService signalHistoryService,
        SignalAuditService signalAuditService)
    {
        _repository = repository;
        _auditRepository = auditRepository;
        _signalHistoryService = signalHistoryService;
        _signalAuditService = signalAuditService;
    }

    [HttpPost("{id:guid}/accept")]
    public async Task<IActionResult> Accept(
        Guid id,
        CancellationToken cancellationToken)
    {
        var signal = await _repository.GetByIdAsync(
            id,
            cancellationToken);

        if (signal is null)
        {
            return NotFound();
        }

        signal.Accept();

        await _auditRepository.AddAsync(
            new SignalAuditEvent(
                signal.Id,
                "Accepted",
                "Signal accepted by human review."),
            cancellationToken);

        await _repository.SaveAsync(
            signal,
            cancellationToken);

        return Ok(signal);
    }

    [HttpPost("{id:guid}/reject")]
    public async Task<IActionResult> Reject(
        Guid id,
        CancellationToken cancellationToken)
    {
        var signal = await _repository.GetByIdAsync(
            id,
            cancellationToken);

        if (signal is null)
        {
            return NotFound();
        }

        signal.Reject();

        await _auditRepository.AddAsync(
            new SignalAuditEvent(
                signal.Id,
                "Rejected",
                "Signal rejected by human review."),
            cancellationToken);

        await _repository.SaveAsync(
            signal,
            cancellationToken);

        return Ok(signal);
    }

    [HttpGet]
    public async Task<IActionResult> GetAll(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 10,
        [FromQuery] SignalStatus? status = null,
        CancellationToken cancellationToken = default)
    {
        var query = new SignalHistoryQuery(
            page,
            pageSize,
            status);

        var result =
            await _signalHistoryService.GetPagedAsync(
                query,
                cancellationToken);

        return Ok(result);
    }

    [HttpGet("status/{status}")]
    public async Task<IActionResult> GetByStatus(
        SignalStatus status,
        CancellationToken cancellationToken)
    {
        var result =
            await _signalHistoryService.GetByStatusAsync(
                status,
                cancellationToken);

        return Ok(result);
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetById(
        Guid id,
        CancellationToken cancellationToken)
    {
        var result =
            await _signalHistoryService.GetByIdAsync(
                id,
                cancellationToken);

        if (result is null)
        {
            return NotFound();
        }

        return Ok(result);
    }

    [HttpGet("{id:guid}/audit")]
    public async Task<IActionResult> GetAudit(
        Guid id,
        CancellationToken cancellationToken)
    {
        var result =
            await _signalAuditService.GetBySignalIdAsync(
                id,
                cancellationToken);

        return Ok(result);
    }
}