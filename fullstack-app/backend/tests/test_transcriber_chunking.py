from app.transcription.transcriber import calculate_audio_chunk_count, should_chunk_audio


def test_duration_over_limit_triggers_chunking_even_when_file_is_small():
    assert should_chunk_audio(file_size_mb=10, duration_seconds=2241.432)


def test_chunk_count_uses_duration_requirement():
    num_chunks, chunks_by_size, chunks_by_duration = calculate_audio_chunk_count(
        file_size_mb=10,
        duration_seconds=2241.432,
    )

    assert chunks_by_size == 1
    assert chunks_by_duration == 2
    assert num_chunks == 2


def test_chunking_uses_stricter_size_or_duration_requirement():
    num_chunks, chunks_by_size, chunks_by_duration = calculate_audio_chunk_count(
        file_size_mb=100,
        duration_seconds=2241.432,
    )

    assert chunks_by_size == 5
    assert chunks_by_duration == 2
    assert num_chunks == 5
