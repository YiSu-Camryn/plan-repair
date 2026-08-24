public ByteBuffer readToByteBuffer(int max) throws IOException {
    Validate.isTrue(max >= 0, "maxSize must be 0 (unlimited) or larger");
    final boolean localCapped = max > 0; // still possibly capped in total stream
    final int bufferSize = localCapped && max < DefaultSize ? max : DefaultSize;
    final byte[] readBuffer = new byte[bufferSize];
    final ByteArrayOutputStream outStream = new ByteArrayOutputStream(bufferSize);
    
    int read;
    int remaining = localCapped ? max : Integer.MAX_VALUE;
    while (true) {
        read = read(readBuffer, 0, Math.min(remaining, bufferSize));
        if (read == -1) break;
        outStream.write(readBuffer, 0, read);
        remaining -= read;
        if (remaining <= 0 && localCapped) break;
    }
    return ByteBuffer.wrap(outStream.toByteArray());
}