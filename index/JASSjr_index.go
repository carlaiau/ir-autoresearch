/*
	JASSjr_index.go
	---------------
	Copyright (c) 2024 Vaughan Kitchen
	Minimalistic BM25 search engine.
	from https://github.com/andrewtrotman/JASSjr
*/

package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"os"
	"strings"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func isAlpha(c byte) bool {
	return ('A' <= c && c <= 'Z') || ('a' <= c && c <= 'z')
}

func isDigit(c byte) bool {
	return '0' <= c && c <= '9'
}

func isAlnum(c byte) bool {
	return isAlpha(c) || isDigit(c)
}

func normalizeToken(token string) string {
	token = strings.ToLower(token)

	switch {
	case len(token) > 4 && strings.HasSuffix(token, "ies"):
		return token[:len(token)-3] + "y"
	case len(token) > 4 && strings.HasSuffix(token, "sses"):
		return token[:len(token)-2]
	case len(token) > 4 && (strings.HasSuffix(token, "ches") || strings.HasSuffix(token, "shes") || strings.HasSuffix(token, "xes") || strings.HasSuffix(token, "zes")):
		return token[:len(token)-2]
	case len(token) > 3 && strings.HasSuffix(token, "s") &&
		!strings.HasSuffix(token, "ss") &&
		!strings.HasSuffix(token, "us") &&
		!strings.HasSuffix(token, "is") &&
		token != "news":
		return token[:len(token)-1]
	default:
		return token
	}
}

func ignoredFieldEnd(tag string) string {
	switch tag {
	case "<DOCNO>":
		return "</DOCNO>"
	case "<DD>":
		return "</DD>"
	case "<SO>":
		return "</SO>"
	case "<IN>":
		return "</IN>"
	case "<DATELINE>":
		return "</DATELINE>"
	default:
		return ""
	}
}

/*
Struct posting
--------------
*/
type posting struct {
	d, tf int32
}

func addPosting(vocab map[string][]posting, docId int32, token string, weight int32) {
	list, ok := vocab[token]
	if !ok {
		vocab[token] = []posting{{docId, weight}}
	} else if list[len(list)-1].d != docId {
		vocab[token] = append(list, posting{docId, weight})
	} else {
		list[len(list)-1].tf += weight
	}
}

/*
Struct lexer
------------
*/
type lexer struct {
	buffer  []byte
	current int
}

/*
lexer.getNext()
------------
One-character lookahead lexical analyser
*/
func (l *lexer) getNext() []byte {
	/*
		Skip over whitespace and punctuation (but not XML tags)
	*/
	for l.current < len(l.buffer) && !isAlnum(l.buffer[l.current]) && l.buffer[l.current] != '<' {
		l.current++
	}

	/*
		A token is either an XML tag '<'..'>' or a sequence of alpha-numerics.
	*/
	start := l.current
	if l.current >= len(l.buffer) {
		return nil
	}

	if isAlnum(l.buffer[l.current]) {
		for l.current < len(l.buffer) && (isAlnum(l.buffer[l.current]) || l.buffer[l.current] == '-') {
			l.current++
		}
	} else if l.buffer[l.current] == '<' {
		for l.current++; l.current < len(l.buffer) && l.buffer[l.current-1] != '>'; l.current++ {
			/* do nothing */
		}
	}
	/*
		Return the token
	*/
	return l.buffer[start:l.current]
}

/*
main()
------
Simple indexer for TREC WSJ collection
*/
func main() {
	// Make sure we have one parameter, the filename
	if len(os.Args) != 2 {
		fmt.Println("Usage: ", os.Args[0], " <infile.xml>")
		os.Exit(0)
	}

	var (
		vocab                = make(map[string][]posting)
		docIds               = make([]string, 0, 128)
		docLengths           = make([]int32, 0, 128)
		docId          int32 = -1
		documentLength int32 = 0
	)

	fh, err := os.Open(os.Args[1])
	check(err)
	defer fh.Close()

	scanner := bufio.NewScanner(fh)
	pushNext := false
	ignoredUntil := ""
	inHeadline := false
	previousHeadlineTerm := ""
	for scanner.Scan() {
		lex := lexer{scanner.Bytes(), 0}
		for token := lex.getNext(); token != nil; token = lex.getNext() {
			token := string(token)
			if token == "<DOC>" {
				/*
					Save the previous document length
				*/
				if docId != -1 {
					docLengths = append(docLengths, documentLength)
				}

				/*
					Move on to the next document
				*/
				docId++
				documentLength = 0
				ignoredUntil = ""
				inHeadline = false
				previousHeadlineTerm = ""

				if docId%1000 == 0 {
					fmt.Println(docId, "documents indexed")
				}
			}
			if token == "<HL>" {
				inHeadline = true
				previousHeadlineTerm = ""
				continue
			}
			if token == "</HL>" {
				inHeadline = false
				previousHeadlineTerm = ""
				continue
			}

			/*
				if the last token we saw was a <DOCNO> then the next token is the primary key
			*/
			if pushNext {
				docIds = append(docIds, token)
				pushNext = false
				continue
			}
			if fieldEnd := ignoredFieldEnd(token); fieldEnd != "" {
				ignoredUntil = fieldEnd
				if token == "<DOCNO>" {
					pushNext = true
				}
				continue
			}
			if token == ignoredUntil {
				ignoredUntil = ""
				continue
			}
			if ignoredUntil != "" {
				continue
			}

			/*
				Don't index XML tags
			*/
			if strings.HasPrefix(token, "<") {
				if inHeadline {
					previousHeadlineTerm = ""
				}
				continue
			}

			/*
				truncate any long tokens at 255 charactes (so that the length can be stored first and in a single byte)
			*/
			if len(token) > 0xFF {
				token = token[:0xFF+1]
			}

			token = normalizeToken(token)

			weight := int32(1)
			if inHeadline {
				weight = 2
			}

			/*
				add the posting to the in-memory index
			*/
			addPosting(vocab, docId, token, weight)
			if inHeadline && previousHeadlineTerm != "" {
				addPosting(vocab, docId, previousHeadlineTerm+"_"+token, 1)
			}

			/*
				compute the document length
			*/
			documentLength += weight
			if inHeadline {
				previousHeadlineTerm = token
			}
		}
	}
	check(scanner.Err())

	/*
		Save the final document length
	*/
	docLengths = append(docLengths, documentLength)

	/*
		tell the user we've got to the end of parsing
	*/
	fmt.Println("Indexed", docId+1, "documents. Serialising...")

	/*
		store the primary keys
	*/
	docIdFile, err := os.Create("docids.bin")
	check(err)
	defer docIdFile.Close()
	docIdWriter := bufio.NewWriter(docIdFile)
	defer docIdWriter.Flush()
	for _, primaryKey := range docIds {
		docIdWriter.WriteString(primaryKey + "\n")
	}

	/*
		serialise the in-memory index to disk
	*/
	postingsFile, err := os.Create("postings.bin")
	check(err)
	defer postingsFile.Close()
	postingsWriter := bufio.NewWriter(postingsFile)
	defer postingsWriter.Flush()
	vocabFile, err := os.Create("vocab.bin")
	check(err)
	defer vocabFile.Close()
	vocabWriter := bufio.NewWriter(vocabFile)
	defer vocabWriter.Flush()

	var where uint32 = 0
	byteBuffer := make([]byte, 4)
	for term, postings := range vocab {
		/*
			write the postings list to one file
		*/
		err = binary.Write(postingsWriter, binary.NativeEndian, postings)
		check(err)

		/*
			write the vocabulary to a second file (one byte length, string, '\0', 4 byte where, 4 byte size)
		*/
		err = vocabWriter.WriteByte(byte(len(term)))
		check(err)
		_, err = vocabWriter.WriteString(term)
		check(err)
		err = vocabWriter.WriteByte(0)
		check(err)
		binary.NativeEndian.PutUint32(byteBuffer, where)
		_, err = vocabWriter.Write(byteBuffer)
		check(err)
		binary.NativeEndian.PutUint32(byteBuffer, uint32(len(postings)*8))
		_, err = vocabWriter.Write(byteBuffer)
		check(err)

		where += uint32(len(postings) * 8)
	}

	/*
		store the document lengths
	*/
	docLengthsFile, err := os.Create("lengths.bin")
	check(err)
	defer docLengthsFile.Close()
	docLengthsWriter := bufio.NewWriter(docLengthsFile)
	defer docLengthsWriter.Flush()
	err = binary.Write(docLengthsWriter, binary.NativeEndian, docLengths)
	check(err)
}
