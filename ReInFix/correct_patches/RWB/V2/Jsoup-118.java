void initialiseParse(Reader input, String baseUri, Parser parser) {
    Validate.notNullParam(input, "input");
    Validate.notNullParam(baseUri, "baseUri");
    Validate.notNull(parser);

    doc = new Document(parser.defaultNamespace(), baseUri);
    doc.parser(parser);
    this.parser = parser;
    settings = parser.settings();
    reader = new CharacterReader(input);
    trackSourceRange = parser.isTrackPosition();
    reader.trackNewlines(parser.isTrackErrors() || trackSourceRange); // when tracking errors or source ranges, enable newline tracking for better legibility
    start = new Token.StartTag(this); // Moved initialization of start before currentToken
    currentToken = new Token.StartTag(this); // Initialized currentToken to avoid NullPointer exceptions
    tokeniser = new Tokeniser(this);
    stack = new ArrayList<>(32);
    seenTags = new HashMap<>();
    this.baseUri = baseUri;
}