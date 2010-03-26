/*
 * DecodDecs.java
 *
 * Created on 24 de Maio de 2007, 17:14
 */

package org.bireme.dia.util;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.lucene.analysis.SimpleAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.Term;
import org.apache.lucene.queryParser.ParseException;
import org.apache.lucene.queryParser.QueryParser;
import org.apache.lucene.search.Hits;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.PhraseQuery;
import org.apache.lucene.search.Query;
import org.apache.lucene.store.RAMDirectory;

import org.apache.log4j.Logger;
import org.apache.log4j.PropertyConfigurator;

/**
 *
 * @author vinicius.andrade
 */
public class DecodDeCS {
    private RAMDirectory directory;
    private IndexSearcher decs;
    private Logger log;
    
    public DecodDeCS(String decsCodePath) throws IOException {
        directory = new RAMDirectory(decsCodePath);
        decs = new IndexSearcher(directory);
        log = Logger.getLogger(this.getClass());
    }
    
    public String decode(String text, String lang) {
        String subcampo, codigo, descritor = "";
        
        Pattern REGEX = Pattern.compile("(\\^[ds])(\\d+)");
        StringBuffer buffer = new StringBuffer();
        
        Matcher matcher = REGEX.matcher(text);
        
        
        while (matcher.find()){
            subcampo= matcher.group(1);
            codigo = matcher.group(2);
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
        // pela express�o regular
        matcher.appendTail(buffer);
        
        return buffer.toString();
    }
    
    public String getDescriptorTerm(String code, String lang) throws IOException{
        String[] descriptorTerm = null;
        String descriptor = null;
        // remove zeros a esquerda do codigo para match com indice de ID do DeCS
        code = code.replaceAll("^0*","");
        
        PhraseQuery query = new PhraseQuery();
        query.add( new Term("id", code) );
        Hits hits = decs.search(query);
        
        log.info("executanto metodo getDescriptorTerm(" + code +")");
        
        if (hits.length() > 0){
            Document doc = hits.doc(0);
            descriptorTerm = doc.getValues("descriptor");
            log.info(descriptorTerm);
            
            if (lang == null || lang.equals("en")){
                descriptor = descriptorTerm[0];
            }else if (lang.equals("es")){
                descriptor = descriptorTerm[1];
            }else{
                descriptor = descriptorTerm[2];
            }
            descriptor = xmlEntity(descriptor);

        }
        
        return descriptor;
    }
    
    public static String xmlEntity(String value){
        StringBuilder encodedValue=new StringBuilder(value.length() + 4);
        
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
