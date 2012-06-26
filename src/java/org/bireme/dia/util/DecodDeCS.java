/*
 * DecodDecs.java
 *
 * Created on 24 de Maio de 2007, 17:14
 */

package org.bireme.dia.util;

import java.io.File;
import java.io.IOException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.Term;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.PhraseQuery;
import org.apache.lucene.search.TopDocs;
import org.apache.lucene.store.RAMDirectory;
import org.apache.lucene.store.SimpleFSDirectory;

/**
 *
 * @author vinicius.andrade
 */
public class DecodDeCS {
    private final RAMDirectory directory;
    private final IndexReader ir;
    private final IndexSearcher decs;
    private final Log log;
    
    public DecodDeCS(String decsCodePath) throws IOException {
        directory = new RAMDirectory(
                                 new SimpleFSDirectory(new File(decsCodePath)));
        ir = IndexReader.open(directory);
        decs = new IndexSearcher(ir);
        log = LogFactory.getLog(this.getClass());
    }
    
    public String decode(String text, String lang) {
        String descritor = "";
        
        final Pattern REGEX = Pattern.compile("(\\^[ds])(\\d+)");
        final StringBuffer buffer = new StringBuffer();        
        final Matcher matcher = REGEX.matcher(text);
                
        while (matcher.find()){
            final String subcampo= matcher.group(1);
            final String codigo = matcher.group(2);
            
            log.info(subcampo + codigo);
            try {
                descritor = getDescriptorTerm(codigo, lang);
            } catch (IOException ex) {
                log.error(ex);
            }
            
            if (descritor == null)
                descritor = subcampo + codigo;
            
            matcher.appendReplacement(buffer, descritor);
        }
        // Adiciona o restante do texto de entrada, não correspondido
        // pela expressão regular
        matcher.appendTail(buffer);
        
        return buffer.toString();
    }
    
    public String getDescriptorTerm(String code, String lang) 
                                                            throws IOException {
        String descriptor = null;
        // remove zeros a esquerda do codigo para match com indice de ID do DeCS
        code = code.replaceAll("^0*","");
        
        final PhraseQuery query = new PhraseQuery();
        query.add( new Term("id", code) );
        final TopDocs hits = decs.search(query, 1);
        
        log.info("executanto metodo getDescriptorTerm(" + code +")");
        
        if (hits.totalHits > 0){
            final Document doc = decs.doc(hits.scoreDocs[0].doc);            
            final String[] descriptorTerm = doc.getValues("descriptor");
            
            log.info(descriptorTerm);
            
            if (lang == null || lang.equals("en")){
                descriptor = descriptorTerm[0];
            } else if (lang.equals("es")){
                descriptor = descriptorTerm[1];
            } else {
                descriptor = descriptorTerm[2];
            }
            descriptor = xmlEntity(descriptor);
        }
        
        return descriptor;
    }
    
    public static String xmlEntity(String value){
        final StringBuilder encodedValue = 
                                          new StringBuilder(value.length() + 4);
        
        for (int j = 0; j < value.length(); j++) {
            char c = value.charAt(j);
            
            if (c == '&') encodedValue.append("&amp;");
            else if (c == '<') encodedValue.append("&lt;");
            else if (c == '>') encodedValue.append("&gt;");
            else if (c == '\'') encodedValue.append("&apos;");
            else if (c == '"') encodedValue.append("&quot;");
            else encodedValue.append(c);
        }
        return encodedValue.toString();
    }        
}
