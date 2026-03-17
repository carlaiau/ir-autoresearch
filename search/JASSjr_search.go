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
const defaultK1 = 0.7 // BM25 k1 parameter
const defaultB = 0.3  // BM25 b parameter
const feedbackDocs = 2
const expansionTerms = 1
const expansionWeight = 0.10

var bm25K1 = defaultK1
var bm25B = defaultB

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

type weightedQueryTerm struct {
	token  string
	weight float64
}

type feedbackCandidate struct {
	token  string
	weight float64
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func floatFromEnv(name string, fallback float64) float64 {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}

	value, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		panic(fmt.Sprintf("%s must be a floating-point number: %v", name, err))
	}
	return value
}

func configureBM25Parameters() {
	bm25K1 = floatFromEnv("JASSJR_BM25_K1", defaultK1)
	bm25B = floatFromEnv("JASSJR_BM25_B", defaultB)

	if bm25K1 < 0 {
		panic("JASSJR_BM25_K1 must be non-negative")
	}
	if bm25B < 0 || bm25B > 1 {
		panic("JASSJR_BM25_B must be between 0 and 1")
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
		offset += strLength + 1 // read the '\0' string terminator

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

func bm25Score(tf float64, docLength int32, averageDocumentLength float64) float64 {
	if averageDocumentLength == 0 {
		return (tf * (bm25K1 + 1)) / (tf + bm25K1)
	}
	return (tf * (bm25K1 + 1)) / (tf + bm25K1*(1-bm25B+bm25B*(float64(docLength)/averageDocumentLength)))
}

func accumulateScores(index loadedIndex, token string, queryWeight float64, rsv []float64, touchedDocs *[]int) {
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
		rsv[d] += queryWeight * idf * bm25Score(tf, index.docLengths[d], index.averageDocumentLength)
	}
}

func scoreQuery(index loadedIndex, queryTerms []weightedQueryTerm, rsv []float64, touchedDocs []int) []int {
	touchedDocs = touchedDocs[:0]
	for _, term := range queryTerms {
		accumulateScores(index, term.token, term.weight, rsv, &touchedDocs)
	}

	return sortResults(rsv, touchedDocs)
}

func sortResults(rsv []float64, touchedDocs []int) []int {
	slices.SortFunc(touchedDocs, func(a, b int) int {
		if diff := cmp.Compare(rsv[b], rsv[a]); diff != 0 {
			return diff
		}
		return cmp.Compare(b, a)
	})

	return touchedDocs
}

func readForwardDocTerms(forwardFile *os.File, forwardOffsets []int64, docID int) map[string]int32 {
	offset := forwardOffsets[docID*2]
	size := forwardOffsets[docID*2+1]
	if size == 0 {
		return nil
	}

	buffer := make([]byte, int(size))
	_, err := forwardFile.ReadAt(buffer, offset)
	check(err)

	docTerms := make(map[string]int32)
	for current := 0; current < len(buffer); {
		strLength := int(buffer[current])
		current++
		term := string(buffer[current : current+strLength])
		current += strLength
		docTerms[term]++
	}
	return docTerms
}

func selectExpansionTerms(index loadedIndex, forwardFile *os.File, forwardOffsets []int64, rankedDocs []int, originalTerms map[string]struct{}) []weightedQueryTerm {
	limit := feedbackDocs
	if len(rankedDocs) < limit {
		limit = len(rankedDocs)
	}

	candidates := make(map[string]feedbackCandidate)
	for rank := 0; rank < limit; rank++ {
		docID := rankedDocs[rank]
		docWeight := 1.0 / float64(rank+1)
		for term, tf := range readForwardDocTerms(forwardFile, forwardOffsets, docID) {
			if _, exists := originalTerms[term]; exists {
				continue
			}

			termDetails, ok := index.dictionary[term]
			if !ok {
				continue
			}
			postings := int(termDetails.size / 8)
			if postings == 0 || postings == index.documentsInCollection {
				continue
			}

			idf := math.Log(float64(index.documentsInCollection) / float64(postings))
			candidate := candidates[term]
			candidate.token = term
			candidate.weight += docWeight * idf * bm25Score(float64(tf), index.docLengths[docID], index.averageDocumentLength)
			candidates[term] = candidate
		}
	}

	selected := make([]feedbackCandidate, 0, len(candidates))
	for _, candidate := range candidates {
		selected = append(selected, candidate)
	}

	slices.SortFunc(selected, func(a, b feedbackCandidate) int {
		if diff := cmp.Compare(b.weight, a.weight); diff != 0 {
			return diff
		}
		return cmp.Compare(a.token, b.token)
	})

	if len(selected) > expansionTerms {
		selected = selected[:expansionTerms]
	}

	expansions := make([]weightedQueryTerm, 0, len(selected))
	for _, candidate := range selected {
		expansions = append(expansions, weightedQueryTerm{token: candidate.token, weight: expansionWeight})
	}
	return expansions
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
	configureBM25Parameters()

	index := loadIndex("lengths.bin", "postings.bin", "vocab.bin")
	defer index.postingsFile.Close()

	/*
	  Read the primary keys
	*/
	primaryKeysAsBytes, err := os.ReadFile("docids.bin")
	check(err)
	// This isn't performant for large files. Prefer bufio.Scanner there
	// But for small files like what we have here it is faster
	primaryKeys := strings.Split(string(primaryKeysAsBytes), "\n")

	/*
	  Read the per-document forward vectors used for pseudo-relevance feedback.
	*/
	forwardOffsetsAsBytes, err := os.ReadFile("forward_offsets.bin")
	check(err)
	forwardOffsets := make([]int64, len(forwardOffsetsAsBytes)/8)
	err = binary.Read(bytes.NewReader(forwardOffsetsAsBytes), binary.NativeEndian, forwardOffsets)
	check(err)
	if len(forwardOffsets) != index.documentsInCollection*2 {
		panic("forward_offsets.bin must contain offset/size pairs for every document")
	}
	forwardFile, err := os.Open("forward.bin")
	check(err)
	defer forwardFile.Close()

	/*
	  Allocate buffers for score accumulation. We only track
	  the documents touched by the current query to avoid
	  sorting the whole collection when most scores are zero.
	*/
	rsv := make([]float64, index.documentsInCollection)
	touchedDocs := make([]int, 0, 1024)

	/*
	  Search (one query per line)
	*/
	stdin := bufio.NewScanner(os.Stdin)
	for stdin.Scan() {
		queryId := 0
		queryTerms := make([]weightedQueryTerm, 0, 16)
		originalTerms := make(map[string]struct{}, 16)
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
			queryTerms = append(queryTerms, weightedQueryTerm{token: token, weight: 1.0})
			originalTerms[token] = struct{}{}
		}

		touchedDocs = scoreQuery(index, queryTerms, rsv, touchedDocs)
		if len(queryTerms) <= 3 {
			expansions := selectExpansionTerms(index, forwardFile, forwardOffsets, touchedDocs, originalTerms)
			if len(expansions) > 0 {
				for _, expansion := range expansions {
					accumulateScores(index, expansion.token, expansion.weight, rsv, &touchedDocs)
				}
				touchedDocs = sortResults(rsv, touchedDocs)
			}
		}

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
