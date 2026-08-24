private UnionCase readNextUnionCase(final StringReader stream) throws IOException {
    stream.mark(2);
    stream.read(); // '('
    int nextInt = stream.read();
    if (nextInt < 0 || nextInt > 65535) {
        throw new IOException("Invalid data in stream");
    }
    char next = (char) nextInt; 
    if (next == ')'|| next == -1) {
        stream.reset();
        return null;
    }
    stream.reset();
    stream.read(); // '('
    final List<Integer> tags = new ArrayList<>();
    Integer nextTag;
    do {
        nextTag = readNumber(stream);
        if (nextTag != null) {
            tags.add(nextTag);
            stream.read(); // ',' or ')'
        }
    } while (nextTag != null);
    stream.read(); // '['
    stream.mark(1);
    nextInt = stream.read();
    if (nextInt < 0 || nextInt > 65535) {
        throw new IOException("Invalid data in stream");
    }
    next = (char) nextInt;
    if (next == ']') {
        return new UnionCase(tags);
    }
    stream.reset();
    return new UnionCase(tags, readBody(getStreamUpToMatchingBracket(stream)));
}