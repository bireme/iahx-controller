  /*
 * DIAServlet.java
 *
 * Created on 15 de Junho de 2007, 16:19
 */

package org.bireme.dia.controller;

import java.io.*;
import java.net.*;
import java.util.ResourceBundle;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.servlet.*;
import javax.servlet.http.*;
import org.apache.commons.httpclient.HttpClient;
import org.apache.commons.httpclient.HttpException;
import org.apache.commons.httpclient.HttpStatus;
import org.apache.commons.httpclient.methods.GetMethod;

import org.apache.log4j.Logger;
import org.bireme.dia.util.DecodDeCS;


/**
 *
 * @author vinicius.andrade
 * @version
 */
public class DIAServlet extends HttpServlet {
    private Logger log;
    
    private String diaServer;
    private String params;
    private DecodDeCS decs;
    private ResourceBundle config;
    
    private String DEFAULT_SERVER= "localhost:8983";
    private static final String DEFAULT_PORT= "8983";
    private static final String CONFIG_FILE = "dia-config";
    private static final Pattern ENCODE_REGEX = Pattern.compile("\\^[ds]\\d+");
    private static final Pattern IDLIST_XML_REGEX = Pattern.compile("<str name=\"id\">([a-zA-Z\\-0-9]*)</str>");
    private static final Pattern IDLIST_JSON_REGEX = Pattern.compile("\"[a-zA-Z]{1,10}\\-[0-9]{1,10}\"");
    
    public void init(ServletConfig servletConfig) throws ServletException {
        super.init(servletConfig);
        log = Logger.getLogger(this.getClass());
        config = ResourceBundle.getBundle(CONFIG_FILE);
        
        try{
            String decsCodePath = getServletContext().getRealPath("/WEB-INF/classes/resources/decs/code") + "/";
            decs = new DecodDeCS(decsCodePath);
        }catch (IOException ex){
            log.fatal("falha ao tentar instanciar o objecto decs");
        }
       
        // verifia no arquivo de configuracao se foi definido o default server 
        try{
            DEFAULT_SERVER = config.getString("default");
        }catch (Exception ex){
            // USA DEFAULT_SERVER STANDARD localhost
        }        
     
        log.info("dia-controller inicializado - usando DEFAULT_SERVER: " + DEFAULT_SERVER);
    }
    
    /** Processes requests for both HTTP <code>GET</code> and <code>POST</code> methods.
     * @param request servlet request
     * @param response servlet response
     */
    protected void processRequest(HttpServletRequest request, HttpServletResponse response)
    throws ServletException, IOException {
        
        // configura para usar UTF-8 no request e response
        request.setCharacterEncoding("utf-8");
        response.setCharacterEncoding("utf-8");
        
        String type = request.getParameter("op");           //operation
        String site = request.getParameter("site");         //site identification (bvs)
        String col = request.getParameter("col");           //colection
        
        // determina qual o dia-server onde esta a cole��o
        setDiaServer(site, col);
        
        if ("search".equals(type)) {
            processSearch(request, response);
        }else if("detail".equals(type)){
            processDetail(request, response);
        }
    }
    
    private void processDetail(HttpServletRequest request, HttpServletResponse response) throws IOException {
        
        String id = request.getParameter("id");
        String lang = request.getParameter("lang");
        String output = "json";
        
        String searchUrl = diaServer + "/select/";
        
        // faz primeira consulta pelo id que retorna uma string contendo a expressão de pesquisa para os documentos relacionados
        String queryString1 = "q=id:\"" + id + "\"" + "&qt=standard&wt=xslt&tr=related_query.xsl";
        String relatedQuery = sendGetCommand(queryString1, searchUrl);
        // realiza decode dos descritores 
        relatedQuery = decs.decode(relatedQuery, lang);
        
        relatedQuery = URLEncoder.encode(relatedQuery, "utf-8");
        
        String queryString2 = "q=" + relatedQuery + "&qt=related&wt=json&json.nl=arrarr";
        
        log.info("processRelated query: " + queryString2);
        
        String result = sendGetCommand(queryString2, searchUrl);
        result = decs.decode(result, lang);
        
        String iahlinks = this.getIAHLinksJSON(result);        
        // concatena o resultado da pesquisa com o servico de iahlinks
        result = "{\"diaServerResponse\":[" + result + "," + iahlinks + "]}";
        
        sendResponse(response, result, output);

    }
    
    private void processSearch(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String queryFormatted, filterFormatted =  null;        
        StringBuilder queryString = new StringBuilder();
        
        String searchUrl = diaServer + "/select/";
        
        String q = request.getParameter("q");
        String fq = request.getParameter("fq");
        String index = request.getParameter("index");
        String lang = request.getParameter("lang");
        String start = request.getParameter("start");
        String sort = request.getParameter("sort");
        String count = request.getParameter("count");
        String output = request.getParameter("output");
        String tag = request.getParameter("tag");
        String decode = request.getParameter("decode");    //flag decode decs descriptors (export xml)     
        
        String fl = request.getParameter("fl");            // facet.limit parameter
        String fb = request.getParameter("fb");            // facet browse field and total (ex. mh:50)

        
        String queryType = this.identifyQueryType(request);
        
        queryString.append("qt=").append(queryType);        //set the query type
        
        // make query parameter 
        queryString.append("&q=");        
        if (q != null && q.equals("") == false){            
            queryFormatted = this.formatQuery(q);
            
            if ( index != null && index.equals("") == false ){
                //adiciona query por indice.  ti:(malaria aviaria)
                queryString.append(index).append(":(" + queryFormatted + ")");
            }else{            
                queryString.append(queryFormatted);
            }    
        } else {
            queryString.append("*:*");                      // if query parameter null then search all documents
        }
        // END make query parameter 
        
        if (fq != null && fq.equals("") == false){
            //queryString.append("&fq=").append(URLEncoder.encode(fq, "utf-8"));
            filterFormatted = this.formatQuery(fq);
            queryString.append("&fq=").append(filterFormatted);
        }
        
        if (start != null && start.equals("") == false){
            queryString.append("&start=").append(start);
        }
        if (sort != null && sort.equals("") == false){
            queryString.append("&sort=").append(sort);
        }
        if (count != null && count.equals("") == false){
            queryString.append("&rows=").append(count);
        }
        if (output != null && output.equals("") == false){
            if (output.equals("xml")){
                queryString.append("&wt=xslt&tr=export-xml.xsl");
            }else if (output.equals("json") || output.equals("rss")){
                queryString.append("&wt=json&json.nl=arrarr");
            }   
        }else{
            output = "html";
        }
        if (tag != null && tag.equals("") == false){
            queryString.append("&tag=").append(tag);
        }
        if (fl != null && fl.equals("") == false){
            queryString.append("&facet.limit=").append(fl);
        }
        if (fb != null && fb.equals("") == false){
            // facet browse by field (ex. mh:50)            
            String[] fbParam = fb.split(":");   
            
            queryString.append("&f.").append(fbParam[0]).append(".facet.limit=").append(fbParam[1]);
        }
        
        //System.out.println("query final: " + queryStringFormatted);
        
        String result = sendGetCommand(queryString.toString(), searchUrl);
        //verifica o flag de decode
        if (decode == null || decode.equals("")){
            decode = "true";
        }
        
        //verifica atraves de regular expression se o resultado contem descritores DeCS codificados
        if (decode.equals("true") && ENCODE_REGEX.matcher(result).find() ){
            log.info("aplicando decod para idioma " + lang);
            result = decs.decode(result, lang);
            
            //retira marcas dos descritores que nao foram decodificados
            result = result.replaceAll("(\\^d)","");
            result = result.replaceAll("\\^s(\\w*)/*", "/$1");
        }
        
        if (output.equals("json") || output.equals("rss")){
           String iahlinks = this.getIAHLinksJSON(result);        
           // concatena o resultado da pesquisa com o servico de iahlinks
           result = "{\"diaServerResponse\":[" + result + "," + iahlinks + "]}";
        }    
        
        sendResponse(response, result, output);
    }
    
    private void sendResponse(HttpServletResponse response, String result, String output) throws IOException{
        
        PrintWriter out = response.getWriter();
        if ( output.equals("xml") || output.equals("html") ){
            response.setContentType("text/xml; charset=utf-8");
        }else{
            response.setContentType("text/plain; charset=utf-8");
        }
        response.setHeader("Cache-Control", "no-cache");
        
        out.println(result);
    }


    /**
     * Retrieve from search result ID list and mount a search to iahlinks collection
     * @param result String
     * @return JSON String
     * @throws IOException
     */
    private String getIAHLinksJSON(String result) throws IOException {
        
        String jsonResponse = "\"nolinks\"";
        String iahLinksServer = "";

        // verifica no arquivo de configuracao se o indice iahlinks esta em outro servidor
        try{
            iahLinksServer = config.getString("iahlinks");
        }catch (Exception ex){
            // caso nao esteja informado usa o padrao
            iahLinksServer = DEFAULT_SERVER;
        }
        
       //adiciona porta do servi�o
       if ( iahLinksServer.indexOf(":") == -1 ){
           iahLinksServer += ":" + DEFAULT_PORT;
        }

        
        String iahLinksUrl = "http://" + iahLinksServer + "/iahlinks/select/";
        log.info(iahLinksUrl);
        
        String query = "wt=json&json.nl=arrarr&q=";
        
        StringBuilder idListQuery = new StringBuilder();
        Matcher matcher = IDLIST_JSON_REGEX.matcher(result);

        while (matcher.find()){
            String id = matcher.group();
            idListQuery.append(id + " ");
        }
        
        if (idListQuery.length() > 0){     
            query += this.formatQuery(idListQuery.toString());

            log.info(idListQuery);
            jsonResponse = sendGetCommand(query, iahLinksUrl);        
            jsonResponse = jsonResponse.replaceFirst("responseHeader", "iahLinks");
        }   
        return jsonResponse;
    }

    /**
     * Send the command to Solr using a GET
     * @param queryString
     * @param url
     * @return
     * @throws IOException
     */
    private String sendGetCommand(String queryString, String url)
    throws IOException {
        String results = null;
        HttpClient client = new HttpClient();
        GetMethod get = new GetMethod(url);
        
        get.setQueryString(queryString.trim());
                
        try {
            // Execute the method.
            int statusCode = client.executeMethod(get);
            
            if (statusCode != HttpStatus.SC_OK) {
                log.fatal("Method failed: " + get.getStatusLine());
            }
            
            String charset = get.getResponseCharSet();
            InputStream responseBodyAsStream = get.getResponseBodyAsStream();
            StringBuilder responseBuffer = new StringBuilder();
            
            BufferedReader reader = new BufferedReader( new
                    InputStreamReader( responseBodyAsStream, charset ) );
            
            // Read the response body.
            String line = null;
            while ( ( line = reader.readLine() ) != null ) {
                responseBuffer.append( line );
            }
            
            results = responseBuffer.toString();
            reader.close();
            responseBodyAsStream.close();
            
        } catch (HttpException e) {
            log.fatal("Fatal protocol violation: " + e.getMessage());
        } catch (IOException e) {
            log.fatal("Fatal transport error: " + e.getMessage());
        } finally {
            // Release the connection.
            get.releaseConnection();
        }
        
        if (results == null){
            results = "<?xml version=\"1.0\"?><response><connection_problem/></response>";
        }
        
        return results;
    }
    
    private void setDiaServer(String site, String col) {
        String server;
        String solr;
        
        // indicate solr app for the request
        solr = "/" + site;
        
        if (col == null || col.equals("") == false )
            solr += "-" + col;
        
        // busca o site informado no arquivo de configuracao para determinar o servidor
        try{
            server = config.getString(site);
        }catch (Exception ex){
            // caso nao esteja informado usa o padrao
            server = DEFAULT_SERVER;
        }
        
        this.diaServer = "http://" + server;
        
        //adiciona porta do servi�o
        if ( server.indexOf(":") == -1 ){
            this.diaServer = diaServer.concat(":" + DEFAULT_PORT);
        }
        this.diaServer = diaServer.concat(solr);
        
        log.info("dia-server: " + this.diaServer);
    }
    
    private String identifyQueryType(HttpServletRequest request) {
        
        String index = request.getParameter("index");
        String q  = request.getParameter("q");
        String qt = request.getParameter("qt");
        
        if (qt != null && qt.equals("") == false){       //if qt parameter is set in request use instead of other
            return qt;
        }

        // dismax query type is standard option if qt paramenter is not present
        qt = "bvs";                                                 
        
        /* versao anterior 20080925
        if (q != null){
            if (q.contains("$") || q.contains("*") || q.contains(":") || q.contains("(")){
                qt = "standard";
            }
        }      
        if ( index != null && !index.equals("")) {
            qt = "standard";
        }
        */

        if (q == null || q.equals("") || q.contains("$") || q.contains("*") || q.contains(":") || q.contains("(")){
            qt = "standard";
        }
        if ( index != null && !index.equals("")) {
            qt = "standard";
        }
        
        return qt;
    }
    
    public String formatQuery(String queryString) throws UnsupportedEncodingException {
        String replacement;
        Pattern p;
        Matcher matcher;
        String queryFormatted;
       
        replacement = "__replacement__";
       
        // Preserve strings between quotation marks
        p = Pattern.compile("\".*?\"");
        matcher = p.matcher(queryString);
        queryFormatted = matcher.replaceAll(replacement);

        // lowercase first to fix problem with wildcards search (SOLR-218)
        queryFormatted = queryFormatted.toLowerCase();
        queryFormatted = queryFormatted.replaceAll("\\$","*"); 
        queryFormatted = queryFormatted.replaceAll(" or "," OR ");
        queryFormatted = queryFormatted.replaceAll(" and not "," NOT ");
        queryFormatted = queryFormatted.replaceAll(" and "," AND ");      
       
        // Put back strings between quotation marks
        matcher.reset();
        while( matcher.find() ){
            queryFormatted = queryFormatted.replaceFirst(replacement,matcher.group(0));
        }
       
        queryFormatted = URLEncoder.encode(queryFormatted, "utf-8");

        return queryFormatted;
    }
    
 // <editor-fold defaultstate="collapsed" desc="HttpServlet methods. Click on the + sign on the left to edit the code.">
    /** Handles the HTTP <code>GET</code> method.
     * @param request servlet request
     * @param response servlet response
     */
    protected void doGet(HttpServletRequest request, HttpServletResponse response)
    throws ServletException, IOException {
        processRequest(request, response);
    }

    /** Handles the HTTP <code>POST</code> method.
     * @param request servlet request
     * @param response servlet response
     */
    protected void doPost(HttpServletRequest request, HttpServletResponse response)
    throws ServletException, IOException {
        processRequest(request, response);
    }

    /** Returns a short description of the servlet.
     */
    public String getServletInfo() {
        return "Short description";
    }
// </editor-fold>


    
}