static URL encodeUrl(URL u) {
    u = punyUrl(u);
    try {
        // Decode the URL before re-encoding it
        String decodedURL = java.net.URLDecoder.decode(u.toString(), "UTF-8");
        URL url = new URL(decodedURL);

        // run the URL through URI, so components are encoded
        URI uri = new URI(url.getProtocol(), url.getUserInfo(), url.getHost(), url.getPort(), url.getPath(), url.getQuery(), url.getRef());

        return uri.toURL();
    } catch (URISyntaxException | MalformedURLException | UnsupportedEncodingException e) {
        // give up and return the original input
        return u;
    }
}