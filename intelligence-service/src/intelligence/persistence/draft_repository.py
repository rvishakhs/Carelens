



async def persist_original_draft(
    session: AsyncSession,
    *,
    claim: ClaimedJob,
    snapshot: JobExecutionSnapshot,
    retrieval: HandoverRetrieval,
    content: ValidatedHandoverContent,
    generation: GenerationMetadata,
) -> UUID:
    ...