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
const headlineB = 0.1
const headlineWeight = 0.35

/*
Struct vocabEntry
-----------------
*/
type vocabEntry struct {
	where, size int32 // where on the disk and how large (in bytes) is the postings list?
}

type loadedIndex struct {
	docLengths            []int32
	averageDocumentLength float64
	documentsInCollection int
	postingsFile          *os.File
	dictionary            map[string]vocabEntry
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func loadIndex(lengthsPath string, postingsPath string, vocabPath string) loadedIndex {
	lengthsAsBytes, err := os.ReadFile(lengthsPath)
	check(err)
	docLengths := make([]int32, len(lengthsAsBytes)/4)
	err = binary.Read(bytes.NewReader(lengthsAsBytes), binary.NativeEndian, docLengths)
	check(err)

	documentsInCollection := len(docLengths)
	averageDocumentLength := 0.0
	for _, which := range docLengths {
		averageDocumentLength += float64(which)
	}
	if documentsInCollection > 0 {
		averageDocumentLength /= float64(documentsInCollection)
	}

	postingsFile, err := os.Open(postingsPath)
	check(err)

	dictionary := make(map[string]vocabEntry)
	vocabAsBytes, err := os.ReadFile(vocabPath)
	check(err)
	for offset := 0; offset < len(vocabAsBytes); {
		strLength := int(vocabAsBytes[offset])
		offset += 1

		term := string(vocabAsBytes[offset : offset+strLength])
		offset += strLength + 1

		where := binary.NativeEndian.Uint32(vocabAsBytes[offset:])
		offset += 4
		size := binary.NativeEndian.Uint32(vocabAsBytes[offset:])
		offset += 4

		dictionary[term] = vocabEntry{int32(where), int32(size)}
	}

	return loadedIndex{
		docLengths:            docLengths,
		averageDocumentLength: averageDocumentLength,
		documentsInCollection: documentsInCollection,
		postingsFile:          postingsFile,
		dictionary:            dictionary,
	}
}

func bm25Score(tf float64, docLength int32, averageDocumentLength float64, b float64) float64 {
	if averageDocumentLength == 0 {
		return tf * (k1 + 1) / (tf + k1)
	}
	return (tf * (k1 + 1)) / (tf + k1*(1-b+b*(float64(docLength)/averageDocumentLength)))
}

func accumulateScores(index loadedIndex, token string, b float64, scoreWeight float64, rsv []float64, touchedDocs *[]int) {
	termDetails, ok := index.dictionary[token]
	if !ok {
		return
	}

	currentListAsBytes := make([]byte, termDetails.size)
	_, err := index.postingsFile.ReadAt(currentListAsBytes, int64(termDetails.where))
	check(err)
	currentList := make([]int32, len(currentListAsBytes)/4)
	err = binary.Read(bytes.NewReader(currentListAsBytes), binary.NativeEndian, currentList)
	check(err)
	postings := len(currentListAsBytes) / 8

	if index.documentsInCollection == postings {
		return
	}

	idf := math.Log(float64(index.documentsInCollection) / float64(postings))

	for i := 0; i < len(currentList); i += 2 {
		d := int(currentList[i])
		tf := float64(currentList[i+1])
		if rsv[d] == 0 {
			*touchedDocs = append(*touchedDocs, d)
		}
		rsv[d] += scoreWeight * idf * bm25Score(tf, index.docLengths[d], index.averageDocumentLength, b)
	}
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

/*
main()
------
Simple search engine ranking on BM25.
*/
func main() {
	fullIndex := loadIndex("lengths.bin", "postings.bin", "vocab.bin")
	defer fullIndex.postingsFile.Close()
	headlineIndex := loadIndex("headline_lengths.bin", "headline_postings.bin", "headline_vocab.bin")
	defer headlineIndex.postingsFile.Close()
	if fullIndex.documentsInCollection != headlineIndex.documentsInCollection {
		panic("full and headline indexes must contain the same number of documents")
	}

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
	/*
	  Allocate buffers for score accumulation. We only track
	  the documents touched by the current query to avoid
	  sorting the whole collection when most scores are zero.
	*/
	rsv := make([]float64, fullIndex.documentsInCollection)
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

			accumulateScores(fullIndex, token, b, 1.0, rsv, &touchedDocs)
			accumulateScores(headlineIndex, token, headlineB, headlineWeight, rsv, &touchedDocs)
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
