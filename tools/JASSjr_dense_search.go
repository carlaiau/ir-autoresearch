package main

import (
	"bufio"
	"bytes"
	"container/heap"
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"slices"
	"strconv"
	"strings"
	"time"
)

const (
	defaultSemanticMode       = "off"
	defaultSemanticModel      = "text-embedding-3-small"
	defaultSemanticDimensions = 512
	defaultSemanticTopK       = 1000
	openAIEmbeddingsURL       = "https://api.openai.com/v1/embeddings"
	maxOpenAIRetries          = 5
)

var retryableHTTPCodes = map[int]struct{}{
	408: {},
	409: {},
	429: {},
	500: {},
	502: {},
	503: {},
	504: {},
}

type denseMeta struct {
	Mode           string `json:"mode"`
	Model          string `json:"model"`
	Dimensions     int    `json:"dimensions"`
	DocWords       int    `json:"doc_words"`
	Documents      int    `json:"documents"`
	Completed      int    `json:"completed_documents"`
	Status         string `json:"status"`
	KeySource      string `json:"key_source"`
	ByteOrder      string `json:"byte_order"`
	VectorFilePath string `json:"vector_file"`
}

type embeddingItem struct {
	Embedding []float64 `json:"embedding"`
	Index     int       `json:"index"`
}

type embeddingsRequest struct {
	Input          []string `json:"input"`
	Model          string   `json:"model"`
	Dimensions     int      `json:"dimensions"`
	EncodingFormat string   `json:"encoding_format"`
}

type embeddingsResponse struct {
	Data  []embeddingItem `json:"data"`
	Usage struct {
		PromptTokens int `json:"prompt_tokens"`
		TotalTokens  int `json:"total_tokens"`
	} `json:"usage"`
}

type queryEntry struct {
	id   string
	text string
}

type scoredDoc struct {
	docIndex int
	score    float64
}

type minHeap []scoredDoc

func (h minHeap) Len() int { return len(h) }

func (h minHeap) Less(i, j int) bool {
	if h[i].score != h[j].score {
		return h[i].score < h[j].score
	}
	return h[i].docIndex > h[j].docIndex
}

func (h minHeap) Swap(i, j int) { h[i], h[j] = h[j], h[i] }

func (h *minHeap) Push(x any) { *h = append(*h, x.(scoredDoc)) }

func (h *minHeap) Pop() any {
	old := *h
	n := len(old)
	item := old[n-1]
	*h = old[:n-1]
	return item
}

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func loadEnvFile(path string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	for _, rawLine := range strings.Split(string(data), "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		if strings.HasPrefix(line, "export ") {
			line = strings.TrimSpace(strings.TrimPrefix(line, "export "))
		}
		parts := strings.SplitN(line, "=", 2)
		name := strings.TrimSpace(parts[0])
		if name == "" || os.Getenv(name) != "" {
			continue
		}
		value := strings.TrimSpace(parts[1])
		if len(value) >= 2 {
			if (value[0] == '"' && value[len(value)-1] == '"') || (value[0] == '\'' && value[len(value)-1] == '\'') {
				value = value[1 : len(value)-1]
			}
		}
		check(os.Setenv(name, value))
	}
}

func loadRepoEnv(repoRoot string) string {
	keySource := "missing"
	if os.Getenv("OPENAI_API_KEY") != "" {
		keySource = "env"
	}
	loadEnvFile(repoRoot + "/.env")
	loadEnvFile(repoRoot + "/.env.local")
	if keySource == "missing" && os.Getenv("OPENAI_API_KEY") != "" {
		return "dotenv"
	}
	return keySource
}

func intFromEnv(name string, fallback int) int {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		panic(fmt.Sprintf("%s must be an integer: %v", name, err))
	}
	return value
}

func loadDocIDs() []string {
	data, err := os.ReadFile("docids.bin")
	check(err)
	lines := strings.Split(string(data), "\n")
	docids := make([]string, 0, len(lines))
	for _, line := range lines {
		if line == "" {
			continue
		}
		docids = append(docids, line)
	}
	return docids
}

func loadDenseMeta() denseMeta {
	data, err := os.ReadFile("dense-docs.meta.json")
	check(err)
	var meta denseMeta
	err = json.Unmarshal(data, &meta)
	check(err)
	return meta
}

func loadDenseVectors(meta denseMeta) []float32 {
	if meta.Status != "complete" {
		panic("dense vectors are incomplete")
	}
	if meta.ByteOrder != "" && meta.ByteOrder != "little" {
		panic("dense vectors must be written in little-endian format")
	}

	filePath := meta.VectorFilePath
	if filePath == "" {
		filePath = "dense-docs.f32"
	}
	file, err := os.Open(filePath)
	check(err)
	defer file.Close()

	vectors := make([]float32, meta.Documents*meta.Dimensions)
	err = binary.Read(file, binary.LittleEndian, vectors)
	check(err)
	return vectors
}

func normalize(values []float64) []float64 {
	norm := 0.0
	for _, value := range values {
		norm += value * value
	}
	if norm == 0 {
		return values
	}
	scale := math.Sqrt(norm)
	result := make([]float64, len(values))
	for index, value := range values {
		result[index] = value / scale
	}
	return result
}

func parseQueries() []queryEntry {
	scanner := bufio.NewScanner(os.Stdin)
	queries := make([]queryEntry, 0, 64)
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		line := scanner.Text()
		parts := strings.Fields(line)
		if len(parts) == 0 {
			continue
		}
		queryID := strconv.Itoa(lineNumber)
		queryText := line
		if parts[0] != "" {
			if _, err := strconv.Atoi(parts[0]); err == nil {
				queryID = parts[0]
				queryText = strings.TrimSpace(strings.TrimPrefix(line, parts[0]))
			}
		}
		if queryText == "" {
			queryText = queryID
		}
		queries = append(queries, queryEntry{id: queryID, text: queryText})
	}
	if err := scanner.Err(); err != nil {
		panic(err)
	}
	return queries
}

func postEmbeddings(apiKey string, requestBody embeddingsRequest) embeddingsResponse {
	payload, err := json.Marshal(requestBody)
	check(err)

	client := &http.Client{Timeout: 2 * time.Minute}
	var response embeddingsResponse
	for attempt := 1; attempt <= maxOpenAIRetries; attempt++ {
		req, err := http.NewRequest(http.MethodPost, openAIEmbeddingsURL, bytes.NewReader(payload))
		check(err)
		req.Header.Set("Authorization", "Bearer "+apiKey)
		req.Header.Set("Content-Type", "application/json")

		httpResponse, err := client.Do(req)
		if err != nil {
			if attempt < maxOpenAIRetries {
				time.Sleep(time.Duration(1<<(attempt-1)) * time.Second)
				continue
			}
			panic(fmt.Sprintf("OpenAI embeddings request failed: %v", err))
		}

		body, readErr := io.ReadAll(httpResponse.Body)
		httpResponse.Body.Close()
		check(readErr)

		if httpResponse.StatusCode >= 200 && httpResponse.StatusCode < 300 {
			err = json.Unmarshal(body, &response)
			check(err)
			return response
		}

		if _, ok := retryableHTTPCodes[httpResponse.StatusCode]; ok && attempt < maxOpenAIRetries {
			time.Sleep(time.Duration(1<<(attempt-1)) * time.Second)
			continue
		}
		panic(fmt.Sprintf("OpenAI embeddings request failed with HTTP %d: %s", httpResponse.StatusCode, string(body)))
	}
	panic("OpenAI embeddings request failed after retries")
}

func embedQueries(apiKey, model string, dimensions int, queries []queryEntry) ([][]float64, int, int) {
	inputs := make([]string, 0, len(queries))
	for _, query := range queries {
		inputs = append(inputs, query.text)
	}

	response := postEmbeddings(apiKey, embeddingsRequest{
		Input:          inputs,
		Model:          model,
		Dimensions:     dimensions,
		EncodingFormat: "float",
	})

	if len(response.Data) != len(queries) {
		panic(fmt.Sprintf("expected %d query embeddings, got %d", len(queries), len(response.Data)))
	}

	slices.SortFunc(response.Data, func(a, b embeddingItem) int {
		return a.Index - b.Index
	})

	embeddings := make([][]float64, len(response.Data))
	for index, item := range response.Data {
		embeddings[index] = normalize(item.Embedding)
	}
	return embeddings, response.Usage.PromptTokens, response.Usage.TotalTokens
}

func topDenseDocs(queryEmbedding []float64, vectors []float32, dimensions int, topK int) []scoredDoc {
	h := &minHeap{}
	heap.Init(h)

	for docIndex := 0; docIndex < len(vectors)/dimensions; docIndex++ {
		base := docIndex * dimensions
		score := 0.0
		for dim := 0; dim < dimensions; dim++ {
			score += queryEmbedding[dim] * float64(vectors[base+dim])
		}

		item := scoredDoc{docIndex: docIndex, score: score}
		if h.Len() < topK {
			heap.Push(h, item)
			continue
		}

		minItem := (*h)[0]
		if score > minItem.score || (score == minItem.score && docIndex < minItem.docIndex) {
			heap.Pop(h)
			heap.Push(h, item)
		}
	}

	results := make([]scoredDoc, h.Len())
	for i := len(results) - 1; i >= 0; i-- {
		results[i] = heap.Pop(h).(scoredDoc)
	}

	slices.SortFunc(results, func(a, b scoredDoc) int {
		if a.score < b.score {
			return 1
		}
		if a.score > b.score {
			return -1
		}
		return a.docIndex - b.docIndex
	})
	return results
}

func writeMetadata(path string, meta denseMeta, keySource string, promptTokens, totalTokens, outputDocs int) {
	if path == "" {
		return
	}
	lines := []string{
		fmt.Sprintf("JASSJR_SEMANTIC_MODE: %s", meta.Mode),
		fmt.Sprintf("JASSJR_SEMANTIC_KEY_SOURCE: %s", keySource),
		fmt.Sprintf("JASSJR_SEMANTIC_MODEL: %s", meta.Model),
		fmt.Sprintf("JASSJR_SEMANTIC_DIMENSIONS: %d", meta.Dimensions),
		fmt.Sprintf("JASSJR_SEMANTIC_DOC_WORDS: %d", meta.DocWords),
		fmt.Sprintf("JASSJR_SEMANTIC_DOCUMENTS: %d", meta.Documents),
		fmt.Sprintf("JASSJR_SEMANTIC_DOC_VECTOR_FILE: %s", meta.VectorFilePath),
		fmt.Sprintf("JASSJR_SEMANTIC_OUTPUT_DOCS: %d", outputDocs),
		fmt.Sprintf("JASSJR_SEMANTIC_PROMPT_TOKENS: %d", promptTokens),
		fmt.Sprintf("JASSJR_SEMANTIC_TOTAL_TOKENS: %d", totalTokens),
	}
	err := os.WriteFile(path, []byte(strings.Join(lines, "\n")+"\n"), 0o644)
	check(err)
}

func main() {
	metadataFile := flag.String("metadata-file", "", "Optional output path for semantic metadata")
	repoRoot := flag.String("repo-root", "", "Repository root for .env loading")
	flag.Parse()

	resolvedRepoRoot := *repoRoot
	if resolvedRepoRoot == "" {
		cwd, err := os.Getwd()
		check(err)
		resolvedRepoRoot = cwd
	}
	keySource := loadRepoEnv(resolvedRepoRoot)

	semanticMode := strings.TrimSpace(os.Getenv("JASSJR_SEMANTIC_MODE"))
	if semanticMode == "" {
		semanticMode = defaultSemanticMode
	}
	if semanticMode != "openai" {
		panic("JASSJR_SEMANTIC_MODE must be openai for dense search")
	}

	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		panic("OPENAI_API_KEY is required for dense search")
	}

	meta := loadDenseMeta()
	docids := loadDocIDs()
	if len(docids) != meta.Documents {
		panic("dense vectors must align to docids.bin order")
	}
	vectors := loadDenseVectors(meta)
	queries := parseQueries()
	if len(queries) == 0 {
		if keySource == "missing" {
			keySource = os.Getenv("JASSJR_OPENAI_KEY_SOURCE")
		}
		writeMetadata(*metadataFile, meta, keySource, 0, 0, defaultSemanticTopK)
		return
	}

	queryEmbeddings, promptTokens, totalTokens := embedQueries(apiKey, meta.Model, meta.Dimensions, queries)
	topK := intFromEnv("JASSJR_SEMANTIC_TOPK", defaultSemanticTopK)
	if topK <= 0 {
		panic("JASSJR_SEMANTIC_TOPK must be positive")
	}

	for index, query := range queries {
		results := topDenseDocs(queryEmbeddings[index], vectors, meta.Dimensions, topK)
		for rank, item := range results {
			fmt.Printf("%s Q0 %s %d %.6f JASSjr\n", query.id, docids[item.docIndex], rank+1, item.score)
		}
	}

	if keySource == "missing" {
		keySource = os.Getenv("JASSJR_OPENAI_KEY_SOURCE")
	}
	if keySource == "" || keySource == "missing" {
		keySource = meta.KeySource
	}
	writeMetadata(*metadataFile, meta, keySource, promptTokens, totalTokens, topK)
}
