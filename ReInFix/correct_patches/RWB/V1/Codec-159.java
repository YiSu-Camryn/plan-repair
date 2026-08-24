@Override
void decode(final byte[] data, int offset, final int length, final Context context) {
    if (context.eof || length < 0) {
        context.eof = true;
        if (context.ibitWorkArea != 0) {
            validateTrailingCharacter();
        }
        return;
    }

    final int dataLen = Math.min(data.length - offset, length);
    final int availableChars = (context.ibitWorkArea != 0 ? 1 : 0) + dataLen;

    // small optimisation to short-cut the rest of this method when it is fed byte-by-byte
    if (availableChars == 1 && availableChars == dataLen) {
        // store 1/2 byte for next invocation of decode, we offset by +1 as empty-value is 0
        context.ibitWorkArea = decodeOctet(data[offset]) + 1;
        return;
    }

    // we must have an even number of chars to decode
    final int charsToProcess = availableChars - (availableChars % BYTES_PER_ENCODED_BLOCK);

    final byte[] buffer = ensureBufferSize(charsToProcess / BYTES_PER_ENCODED_BLOCK, context);

    int result;
    int i = 0;
    if (availableChars > dataLen) {
        // we have 1/2 byte from previous invocation to decode
        result = (context.ibitWorkArea - 1) << BITS_PER_ENCODED_BYTE;
        result |= decodeOctet(data[offset++]);
        i = 2;

        buffer[context.pos++] = (byte)result;

        // reset to empty-value for next invocation!
        context.ibitWorkArea = 0;
    }

    while (i < charsToProcess) {
        result = decodeOctet(data[offset++]) << BITS_PER_ENCODED_BYTE;
        result |= decodeOctet(data[offset++]);
        i += 2;
        buffer[context.pos++] = (byte)result;
    }

    // we have one char of a hex-pair left over
    if (i < availableChars) {
        // store 1/2 byte for next invocation of decode, we offset by +1 as empty-value is 0
        context.ibitWorkArea = decodeOctet(data[i]) + 1;
    }
}