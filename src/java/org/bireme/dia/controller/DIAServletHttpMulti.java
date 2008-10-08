  /*
 * DIAServlet.java
 *
 * Created on 15 de Junho de 2007, 16:19
 */

package org.bireme.dia.controller;

import java.io.*;
import java.net.*;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.ResourceBundle;
import java.util.regex.Pattern;

import javax.servlet.*;
import javax.servlet.http.*;
import org.apache.commons.httpclient.*;
import org.apache.commons.httpclient.HttpException;
import org.apache.commons.httpclient.HttpStatus;
import org.apache.commons.httpclient.methods.GetMethod;
import org.apache.commons.httpclient.params.HttpConnectionManagerParams;

import org.apache.log4j.Logger;
import org.apache.log4j.PropertyConfigurator;
import org.bireme.dia.util.DecodDeCS;


/**
 *
 * @author vinicius.andrade
 * @version
 */
public class DIAServletHttpMulti extends HttpServlet {
    private Logger log;
    
    private String diaServer;
    private String params;
    private DecodDeCS decs;
    private ResourceBundle config;
    private HttpClient httpClient;
    private MultiThreadedHttpConnectionManager
            manager = new MultiThreadedHttpConnectionManager();
    private int timeout = 12000;               // default connection timeout msecs
    
    
    private static final String DEFAULT_SERVER= "localhost:8983";
    private static final String DEFAULT_PORT= "8983";
    private static final String CONFIG_FILE = "dia-config";
    private static final Pattern ENCODE_REGEX = Pattern.compile("\\^[ds]\\d+");
    
    public void init(ServletConfig servletConfig) throws ServletException {
        super.init(servletConfig);
        log = Logger.getLogger(this.getClass());
        config = ResourceBundle.getBundle(CONFIG_FILE);

        //Configure HttpManager
        HttpConnectionManagerParams connectionManagerParams =
                new HttpConnectionManagerParams();
        connectionManagerParams.setDefaultMaxConnectionsPerHost(200);
        manager.setParams(connectionManagerParams);
        
        // Create an instance of HttpClient 
        httpClient = new HttpClient(this.manager);
        
        //Timeout until a connection is etablished
        httpClient.getHttpConnectionManager().getParams().setConnectionTimeout(this.timeout);
        //Timeout for waiting for dat
        httpClient.getHttpConnectionManager().getParams().setSoTimeout(this.timeout);
        

        try{
            String decsCodePath = getServletContext().getRealPath("/WEB-INF/classes/resources/decs/code") + "/";
            decs = new DecodDeCS(decsCodePath);
        }catch (IOException ex){
            log.fatal("falha ao tentar instanciar o objecto decs");
        }
        
        log.info("dia-controller inicializado");
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
        }
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
    
    private void processSearch(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String queryStringFormatted = null;        
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

        String queryType = this.identifyQueryType(request);
        
        queryString.append("qt=").append(queryType);        //set the query type
        
        if (q != null && q.equals("") == false){
            q = q.replaceAll("/\\&/","%26");
            String queryUTF8 = URLEncoder.encode(q, "utf-8");
            
            queryString.append("&q=");
            if ( index != null && index.equals("") == false ){
                //adiciona query por indice.  ti:(malaria aviaria)
                queryString.append(index).append(": (" + queryUTF8 + ")");
            }else{            
                queryString.append(queryUTF8);
            }    
        }

        if (fq != null && fq.equals("") == false){
            queryString.append("&fq=").append(URLEncoder.encode(fq, "utf-8"));
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
            }else if(output.equals("rss")){
                queryString.append("&wt=xslt&tr=export-rss.xsl");
            }            
        }
        if (tag != null && tag.equals("") == false){
            queryString.append("&tag=").append(tag);
        }
        
        queryStringFormatted = this.formatQuery(queryString.toString());
        
        //System.out.println("query final: " + queryStringFormatted);
        
        String result = sendGetCommand(queryStringFormatted, searchUrl);
        
        //verifica atraves de regular expression se o resultado contem descritores DeCS codificados
        if ( ENCODE_REGEX.matcher(result).find() ){
            log.info("aplicando decod para idioma " + lang);
            result = decs.decode(result, lang);
            //retira marcas que separam descritor e qualificador dos termos n�o foram decodificados
            result = result.replaceAll("(\\^d|\\^s)","");
        }
        sendResponse(response, result);
    }
    
    private void sendResponse(HttpServletResponse response, String result) throws IOException{
        
        PrintWriter out = response.getWriter();
        response.setContentType("text/xml; charset=utf-8");
        response.setHeader("Cache-Control", "no-cache");
        
        out.println(result);
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

        GetMethod get = new GetMethod(url);
        queryString = queryString.replaceAll(" ","+");
        
        get.setQueryString(queryString.trim());
                
        try {
            // Execute the method.
            int statusCode = httpClient.executeMethod(get);
            
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
            results = "<?xml version=\"1.0\"?><response><connection-problem/></response>";
        }
        
        return results;
    }
    
    private void setDiaServer(String site, String col) {
        String server;
        String solr;
        
        // indicate solr app for the request
        solr = "/" + site + "-" + col;
        
        // busca o site informado no arquivo de configuracao para determinar o servidor
        try{
            server = config.getString(site);
        }catch (Exception ex){
            // caso n�o esteja informado usa o padr�o
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
        String qt = "bvs";
        
        String index = request.getParameter("index");
        String q = request.getParameter("q");
        
        if (q != null){
            if (q.contains("$") || q.contains("*") || q.contains(":")){
                qt = "standard";
            }
        }      
        if ( index != null && !index.equals("")) {
            qt = "standard";
        }
        
        return qt;
    }
    
    private String formatQuery(String queryString) {
        String queryStringFormatted = null;
        
        queryStringFormatted = queryString.replaceAll(" ","+");
        queryStringFormatted = queryString.replaceAll("\\$","*");
        
        return queryStringFormatted;
    }
    
}