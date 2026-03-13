/*
	JASSjr_search.go
	----------------
	Copyright (c) 2024 Vaughan Kitchen
	Minimalistic BM25 search engine.
	from https://github.com/andrewtrotman/JASSjr
*/

package main

import (
	"bufio"
	"bytes"
	"cmp"
	"encoding/binary"
	"fmt"
	"math"
	"os"
	"slices"
	"strconv"
	"strings"
)

/*
Constants
---------
*/
const k1 = 0.9 // BM25 k1 parameter
const b = 0.3  // BM25 b parameter

/*
Struct vocabEntry
-----------------
*/
type vocabEntry struct {
	where, size int32 // where on the disk and how large (in bytes) is the postings list?
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func hasVowel(token string) bool {
	for i := 0; i < len(token); i++ {
		switch token[i] {
		case 'a', 'e', 'i', 'o', 'u':
			return true
		case 'y':
			if i > 0 {
				return true
			}
		}
	}
	return false
}

func isConsonant(c byte) bool {
	return 'a' <= c && c <= 'z' && !strings.ContainsRune("aeiou", rune(c))
}

func trimDoubleConsonant(token string) string {
	if len(token) < 2 {
		return token
	}
	last := token[len(token)-1]
	if last == token[len(token)-2] && isConsonant(last) && last != 'l' && last != 's' && last != 'z' {
		return token[:len(token)-1]
	}
	return token
}

func normalizeVerbSuffix(token string) string {
	switch {
	case len(token) > 5 && strings.HasSuffix(token, "ied"):
		return token[:len(token)-3] + "y"
	case len(token) > 5 && strings.HasSuffix(token, "ing"):
		stem := token[:len(token)-3]
		if !hasVowel(stem) {
			return token
		}
		switch {
		case strings.HasSuffix(stem, "at"), strings.HasSuffix(stem, "bl"), strings.HasSuffix(stem, "iz"):
			return stem + "e"
		default:
			return trimDoubleConsonant(stem)
		}
	case len(token) > 4 && strings.HasSuffix(token, "ed"):
		stem := token[:len(token)-2]
		if !hasVowel(stem) {
			return token
		}
		switch {
		case strings.HasSuffix(stem, "at"), strings.HasSuffix(stem, "bl"), strings.HasSuffix(stem, "iz"):
			return stem + "e"
		default:
			return trimDoubleConsonant(stem)
		}
	default:
		return token
	}
}

func normalizeToken(token string) string {
	token = strings.ToLower(token)

	switch {
	case len(token) > 4 && strings.HasSuffix(token, "ies"):
		token = token[:len(token)-3] + "y"
	case len(token) > 4 && strings.HasSuffix(token, "sses"):
		token = token[:len(token)-2]
	case len(token) > 4 && (strings.HasSuffix(token, "ches") || strings.HasSuffix(token, "shes") || strings.HasSuffix(token, "xes") || strings.HasSuffix(token, "zes")):
		token = token[:len(token)-2]
	case len(token) > 3 && strings.HasSuffix(token, "s") &&
		!strings.HasSuffix(token, "ss") &&
		!strings.HasSuffix(token, "us") &&
		!strings.HasSuffix(token, "is") &&
		token != "news":
		token = token[:len(token)-1]
	default:
	}

	return normalizeVerbSuffix(token)
}

/*
main()
------
Simple search engine ranking on BM25.
*/
func main() {
	/*
	  Read the document lengths
	*/
	lengthsAsBytes, err := os.ReadFile("lengths.bin")
	check(err)
	docLengths := make([]int32, len(lengthsAsBytes)/4)
	err = binary.Read(bytes.NewReader(lengthsAsBytes), binary.NativeEndian, docLengths)
	check(err)

	/*
	  Compute the average document length for BM25
	*/
	documentsInCollection := len(docLengths)
	var averageDocumentLength float64 = 0
	for _, which := range docLengths {
		averageDocumentLength += float64(which)
	}
	averageDocumentLength /= float64(documentsInCollection)

	/*
	  Read the primary keys
	*/
	primaryKeysAsBytes, err := os.ReadFile("docids.bin")
	check(err)
	// This isn't performant for large files. Prefer bufio.Scanner there
	// But for small files like what we have here it is faster
	primaryKeys := strings.Split(string(primaryKeysAsBytes), "\n")

	/*
	  Open the postings list file
	*/
	postingsFile, err := os.Open("postings.bin")
	check(err)

	/*
	  Build the vocabulary in memory
	*/
	dictionary := make(map[string]vocabEntry) // the vocab
	vocabAsBytes, err := os.ReadFile("vocab.bin")
	check(err)
	for offset := 0; offset < len(vocabAsBytes); {
		strLength := int(vocabAsBytes[offset])
		offset += 1

		term := string(vocabAsBytes[offset : offset+strLength])
		offset += strLength + 1 // read the '\0' string terminator

		where := binary.NativeEndian.Uint32(vocabAsBytes[offset:])
		offset += 4
		size := binary.NativeEndian.Uint32(vocabAsBytes[offset:])
		offset += 4

		dictionary[term] = vocabEntry{int32(where), int32(size)}
	}

	/*
	  Allocate buffers for score accumulation. We only track
	  the documents touched by the current query to avoid
	  sorting the whole collection when most scores are zero.
	*/
	rsv := make([]float64, documentsInCollection)
	touchedDocs := make([]int, 0, 1024)

	/*
	  Search (one query per line)
	*/
	stdin := bufio.NewScanner(os.Stdin)
	for stdin.Scan() {
		touchedDocs = touchedDocs[:0]
		queryId := 0
		for i, token := range strings.Fields(stdin.Text()) {
			/*
			  If the first token is a number then assume a TREC query number, and skip it
			*/
			if i == 0 {
				if num, err := strconv.Atoi(token); err == nil {
					queryId = num
					continue
				}
			}

			token = normalizeToken(token)

			/*
			  Does the term exist in the collection?
			*/
			termDetails, ok := dictionary[token]
			if !ok {
				continue
			}

			/*
			  Seek and read the postings list
			*/
			currentListAsBytes := make([]byte, termDetails.size)
			_, err := postingsFile.ReadAt(currentListAsBytes, int64(termDetails.where))
			check(err)
			currentList := make([]int32, len(currentListAsBytes)/4)
			err = binary.Read(bytes.NewReader(currentListAsBytes), binary.NativeEndian, currentList)
			check(err)
			postings := len(currentListAsBytes) / 8

			/*
			  Compute the IDF component of BM25 as log(N/n).
			  if IDF == 0 then don't process this postings list as the BM25 contribution of this term will be zero.
			*/
			if documentsInCollection == postings {
				continue
			}

			idf := math.Log(float64(documentsInCollection) / float64(postings))

			/*
			  Process the postings list by simply adding the BM25 component for this document into the accumulators array
			*/
			for i := 0; i < len(currentList); i += 2 {
				d := int(currentList[i])
				tf := float64(currentList[i+1])
				if rsv[d] == 0 {
					touchedDocs = append(touchedDocs, d)
				}
				rsv[d] += idf * ((tf * (k1 + 1)) / (tf + k1*(1-b+b*(float64(docLengths[d])/averageDocumentLength))))
			}
		}
		/*
		  Sort the results list
		*/
		slices.SortFunc(touchedDocs, func(a, b int) int {
			if diff := cmp.Compare(rsv[b], rsv[a]); diff != 0 {
				return diff
			}
			return cmp.Compare(b, a)
		})

		/*
		  Print the (at most) top 1000 documents in the results list in TREC eval format which is:
		  query-id Q0 document-id rank score run-name
		*/
		for i, r := range touchedDocs {
			if i == 1000 {
				break
			}
			fmt.Printf("%d Q0 %s %d %.4f JASSjr\n", queryId, primaryKeys[r], i+1, rsv[r])
		}
		for _, d := range touchedDocs {
			rsv[d] = 0
		}
	}
	if err := stdin.Err(); err != nil {
		panic(err)
	}
}
