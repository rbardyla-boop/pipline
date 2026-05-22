export interface ArticleExtraction {
    title: string;
    body: string;
    url?: string;
}

export function extractArticle(html: string): ArticleExtraction {
    return {
        title: '',
        body: '',
        url: undefined
    };
}
