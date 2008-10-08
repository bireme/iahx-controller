/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package org.bireme.dia.controller;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 *
 * @author vinicius
 */
public class Test {

    public static void main(String[] args) {

/*
        CharSequence inputStr = "<str name=\"id\">lil-1010</str>lasjflasdjfasldjfa<str name=\"id\">lil-99900</str>afasfsdafdsdfa<str name=\"id\">mdl-90-88</str>";
        String patternStr = "<str name=\"id\">([a-zA-Z\\-0-9]*)</str>";

        // Compile and use regular expression
        Pattern pattern = Pattern.compile(patternStr);
        Matcher matcher = pattern.matcher(inputStr);

        while (matcher.find()){
            String groupStr = matcher.group(1);
            System.out.println(groupStr);
        }
  */
        String json = "{\"responseHeader\":{\"status\":0,\"QTime\":1,\"params\":{\"json.nl\":\"arr}";
        json = json.replaceFirst("responseHeader", "iahLinks");
        
        System.out.println(json);

    }
}
