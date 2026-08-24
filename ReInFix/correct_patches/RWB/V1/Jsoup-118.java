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
    reader.trackNewlines(parser.isTrackErrors() || trackSourceRange); 
    tokeniser = new Tokeniser(this);
    stack = new ArrayList<>(32);
    seenTags = new HashMap<>();
    start = new Token.StartTag(this);
    this.baseUri = baseUri;
}